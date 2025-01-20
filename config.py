import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    reader_token: str
    openai_token: str
    github_token: str
    email_recipient: str
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    substack_username: str
    substack_password: str
    github_repo: str
    github_owner: str

    @classmethod
    def from_env(cls):
        return cls(
            reader_token=os.getenv('READER_TOKEN'),
            openai_token=os.getenv('OPENAI_TOKEN'),
            github_token=os.getenv('GITHUB_TOKEN'),
            email_recipient=os.getenv('EMAIL_RECIPIENT'),
            smtp_server=os.getenv('SMTP_SERVER'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_username=os.getenv('SMTP_USERNAME'),
            smtp_password=os.getenv('SMTP_PASSWORD'),
            substack_username=os.getenv('SUBSTACK_USERNAME'),
            substack_password=os.getenv('SUBSTACK_PASSWORD'),
            github_repo=os.getenv('GITHUB_REPO'),
            github_owner=os.getenv('GITHUB_OWNER')
        )