"""Disposable browser fixture, never an email-delivery production option.

Requires an explicit opt-in, a NEW named temporary directory and loopback port.
The private synthetic mailbox is readable by the test driver only, not HTTP.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--storage",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args=parser.parse_args()
    storage=args.storage.resolve()
    if os.environ.get("CIVORA_RUN_DISPOSABLE_FIXTURE")!="1" or not storage.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not storage.name.startswith("civora-ui-fixture-"):
        raise RuntimeError("Refusing a non-temporary/non-opted-in fixture.")
    if not 1024<=args.port<=65535:raise ValueError("Invalid local fixture port.")
    storage.mkdir(mode=0o700,exist_ok=False)
    os.environ.update(PERFORMANCE_AI_STORAGE_DIR=str(storage),DATABASE_URL="",CIVORA_AI_PROVIDER="none",CIVORA_IMAGE_PROVIDER="none",CIVORA_DISABLE_CHAT_LEARNING="1",CIVORA_PRODUCT_MODE="private_alpha")
    import importlib
    import uvicorn
    from backend.services.email_delivery import FakeEmailSender
    from backend.services.identity_proofs import IdentityProofStore
    api=importlib.import_module("backend.api.app")
    class PrivateMailbox(FakeEmailSender):
        def send(self,message):
            if not message.recipient.endswith("@example.test"):raise ValueError("Synthetic email addresses only.")
            super().send(message)
            descriptor=os.open(storage/"mailbox.json",os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600)
            with os.fdopen(descriptor,"w") as stream:
                json.dump([{"recipient":mail.recipient,"text":mail.text} for mail in self.messages],stream)
    api.IDENTITY_PROOFS=IdentityProofStore(api.DB,sender=PrivateMailbox())
    owner=api.AUTH_STORE.register_user(email="owner@example.test",password="Synthetic-only-123",name="Synthetic owner")["user"]
    api.AUTH_STORE.register_user(email="recipient@example.test",password="Pre-registration-password",name="Synthetic unverified account")
    api.PROJECT_STORE.save_project(user_id=owner["user_id"],project_id=None,name="Shared synthetic site",project_input={"manual_fields":{"units":"ft","site_objects":[{"id":"synthetic-office","type":"office_building","x":10,"y":10,"w":30,"d":20}]}})
    uvicorn.run(api.app,host="127.0.0.1",port=args.port,log_level="warning")


if __name__=="__main__":main()
