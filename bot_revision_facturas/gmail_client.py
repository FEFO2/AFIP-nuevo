from __future__ import annotations

import base64
import mimetypes
import re
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Iterable

READONLY_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
AUTOMATION_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GmailClient:
    def __init__(
        self, client_secret_path: Path, token_path: Path, *, readonly: bool = False
    ) -> None:
        self.client_secret_path = client_secret_path
        self.token_path = token_path
        self.scopes = READONLY_SCOPES if readonly else AUTOMATION_SCOPES
        self._service: Any | None = None

    @property
    def service(self) -> Any:
        if self._service is None:
            try:
                from googleapiclient.discovery import build
            except ImportError as error:
                raise RuntimeError(
                    "Faltan las librerias de Gmail. Ejecuta: "
                    "pip install -r bot_revision_facturas/requirements.txt"
                ) from error
            self._service = build(
                "gmail", "v1", credentials=self._load_credentials(), cache_discovery=False
            )
        return self._service

    def _load_credentials(self) -> Any:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as error:
            raise RuntimeError(
                "Faltan las librerias de Gmail. Ejecuta: "
                "pip install -r bot_revision_facturas/requirements.txt"
            ) from error

        credentials = None
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)
        if credentials and credentials.valid and credentials.has_scopes(self.scopes):
            return credentials
        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
            and credentials.has_scopes(self.scopes)
        ):
            credentials.refresh(Request())
        else:
            if not self.client_secret_path.exists():
                raise FileNotFoundError(f"No se encontro {self.client_secret_path}.")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secret_path), self.scopes
            )
            credentials = flow.run_local_server(port=0)

        self.token_path.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

    def profile_email(self) -> str:
        return self.service.users().getProfile(userId="me").execute()["emailAddress"]

    def find_unread_invoices(self, sender: str, subject: str) -> list[dict[str, Any]]:
        query = f'in:inbox is:unread from:{sender} subject:"{subject}" has:attachment'
        messages: list[dict[str, Any]] = []
        page_token = None
        while True:
            response = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token)
                .execute()
            )
            messages.extend(response.get("messages", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        exact: list[dict[str, Any]] = []
        for reference in messages:
            message = self.get_message(reference["id"])
            headers = self.headers(message)
            if headers.get("subject", "").strip().casefold() != subject.casefold():
                continue
            if parseaddr(headers.get("from", ""))[1].casefold() != sender.casefold():
                continue
            exact.append(message)
        return exact

    def get_message(self, message_id: str) -> dict[str, Any]:
        return (
            self.service.users().messages().get(userId="me", id=message_id, format="full").execute()
        )

    @staticmethod
    def headers(message: dict[str, Any]) -> dict[str, str]:
        return {
            header["name"].lower(): header["value"]
            for header in message.get("payload", {}).get("headers", [])
        }

    def download_attachments(self, message: dict[str, Any], destination: Path) -> list[Path]:
        destination.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []

        def walk(parts: Iterable[dict[str, Any]]) -> None:
            for part in parts:
                filename = Path(part.get("filename") or "").name
                body = part.get("body", {})
                if filename:
                    safe_name = re.sub(r"[^\w.() -]", "_", filename, flags=re.UNICODE)
                    data = body.get("data")
                    attachment_id = body.get("attachmentId")
                    if attachment_id:
                        response = (
                            self.service.users()
                            .messages()
                            .attachments()
                            .get(userId="me", messageId=message["id"], id=attachment_id)
                            .execute()
                        )
                        data = response["data"]
                    if data:
                        path = destination / safe_name
                        path.write_bytes(base64.urlsafe_b64decode(data.encode("ascii")))
                        paths.append(path)
                if part.get("parts"):
                    walk(part["parts"])

        payload = message.get("payload", {})
        walk(payload.get("parts", [payload]))
        return paths

    def mark_read(self, message_id: str) -> None:
        self._modify(message_id, remove=["UNREAD"])

    def archive_read(self, message_id: str) -> None:
        self._modify(message_id, remove=["UNREAD", "INBOX"])

    def _modify(self, message_id: str, *, remove: list[str]) -> None:
        (
            self.service.users()
            .messages()
            .modify(userId="me", id=message_id, body={"removeLabelIds": remove})
            .execute()
        )

    def create_difference_draft(
        self,
        *,
        recipient: str,
        source_message: dict[str, Any],
        body: str,
        attachments: Iterable[Path],
    ) -> str:
        message = EmailMessage()
        headers = self.headers(source_message)
        message["To"] = recipient
        subject = headers.get("subject", "")
        message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if headers.get("message-id"):
            message["In-Reply-To"] = headers["message-id"]
            message["References"] = " ".join(
                value for value in (headers.get("references", ""), headers["message-id"]) if value
            )
        message.set_content(body)

        for path in attachments:
            mime_type, _ = mimetypes.guess_type(path.name)
            main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
            message.add_attachment(
                path.read_bytes(), maintype=main_type, subtype=sub_type, filename=path.name
            )

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        response = (
            self.service.users()
            .drafts()
            .create(
                userId="me", body={"message": {"raw": raw, "threadId": source_message["threadId"]}}
            )
            .execute()
        )
        return response["id"]
