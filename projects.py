#!/usr/bin/env python3

import base64
import builtins
import contextlib
import email.message
import email.parser
import email.policy
import json
import os
import smtplib
import subprocess
import sys
import tempfile
import uuid

class ProjectsApp:

    """
    Email processing
    ================

    I can process emails:

    >>> database = ProjectsApp.run_in_test_mode(
    ...     args=["process_email"],
    ...     stdin=Email.create_test_instance(
    ...         to_address="timeline@projects.rickardlindberg.me"
    ...     ).render(),
    ...     database_inits=[
    ...         lambda db: db.project("timeline").create(),
    ...     ]
    ... )

    >>> len(database.project("timeline").load()["conversations"])
    1

    NOTE: We just want to assert that the email was processed somehow. Details
    of email processing is implemented and tested in EmailProcessor.

    Project creation
    ================

    I can create projects:

    >>> database = ProjectsApp.run_in_test_mode(
    ...     args=["create_project", "timeline"],
    ... )
    >>> database.project("timeline").load()
    {}

    Project watching
    ================

    I can add watchers to a project project:

    >>> database = ProjectsApp.run_in_test_mode(
    ...     args=["watch_project", "timeline", "watcher@example.com"],
    ...     database_inits=[
    ...         lambda db: db.project("timeline").create(),
    ...     ]
    ... )
    >>> database.project("timeline").load()["watchers"]
    ['watcher@example.com']

    Unknown commands
    ================

    I fail if command is unknown:

    >>> ProjectsApp.run_in_test_mode(
    ...     args=["unknown_command"],
    ... )
    Traceback (most recent call last):
        ...
    SystemExit: Unknown command ['unknown_command']

    Instantiation
    =============

    I can instantiate myself:

    >>> isinstance(ProjectsApp.create(), ProjectsApp)
    True
    """

    @staticmethod
    def create():
        return ProjectsApp(
            args=Args.create(),
            stdin=Stdin.create(),
            database=Database(JsonStore(
                filesystem=Filesystem.create(),
                uuid=UUID.create(),
            )),
            smtp_server=SMTPServer.create()
        )

    @staticmethod
    def run_in_test_mode(args=[], stdin=b"", database_inits=[]):
        database = Database(JsonStore(
            filesystem=Filesystem.create_null(),
            uuid=UUID.create_null()
        ))
        for x in database_inits:
            x(database)
        app = ProjectsApp(
            args=Args.create_null(args),
            stdin=Stdin.create_null(stdin),
            database=database,
            smtp_server=SMTPServer.create_null()
        )
        app.run()
        return database

    def __init__(self, args, stdin, database, smtp_server):
        self.args = args
        self.stdin = stdin
        self.database = database
        self.smtp_server = smtp_server

    def run(self):
        if self.args.get() == ["process_email"]:
            return EmailProcessor(
                database=self.database,
                smtp_server=self.smtp_server
            ).process(self.stdin.read())
        elif self.args.get()[:1] == ["create_project"]:
            name = self.args.get()[1]
            self.database.project(name).create()
        elif self.args.get()[:1] == ["watch_project"]:
            name, email = self.args.get()[1:]
            self.database.project(name).add_watcher(email)
        else:
            sys.exit(f"Unknown command {self.args.get()}")

class EmailProcessor:

    @staticmethod
    def create_test_instance():
        events = Events()
        database = Database(JsonStore(
            filesystem=events.track(Filesystem.create_null()),
            uuid=UUID.create_null()
        ))
        smtp_server = events.track(SMTPServer.create_null())
        processor = EmailProcessor(
            database=database,
            smtp_server=smtp_server,
        )
        return database, events, processor

    def __init__(self, database, smtp_server):
        self.db = database
        self.smtp_server = smtp_server

    def process(self, raw_email):
        """
        I create a new conversation in a project:

        >>> database, events, processor = EmailProcessor.create_test_instance()
        >>> database.project("timeline").create()
        >>> database.project("timeline").add_watcher("watcher1@example.com")
        >>> database.project("timeline").add_watcher("watcher2@example.com")

        >>> raw_email = Email.create_test_instance(
        ...     to_address="timeline@projects.rickardlindberg.me",
        ...     subject="Hello World!",
        ...     body="hello",
        ... ).render()
        >>> processor.process(raw_email)

        >>> events.filter("EMAIL_SENT")
        EMAIL_SENT =>
            from: 'timeline@projects.rickardlindberg.me'
            to: 'watcher1@example.com'
            reply-to: 'timeline+uuid3@projects.rickardlindberg.me'
            subject: 'Hello World!'
            body: 'hello\\n'
        EMAIL_SENT =>
            from: 'timeline@projects.rickardlindberg.me'
            to: 'watcher2@example.com'
            reply-to: 'timeline+uuid3@projects.rickardlindberg.me'
            subject: 'Hello World!'
            body: 'hello\\n'

        >>> events.filter("FILE_WRITTEN")
        FILE_WRITTEN =>
            path: 'projects/timeline/index.json'
            contents: '{}'
        FILE_WRITTEN =>
            path: 'projects/timeline/index.json'
            contents: '{"watchers": ["watcher1@example.com"]}'
        FILE_WRITTEN =>
            path: 'projects/timeline/index.json'
            contents: '{"watchers": ["watcher1@example.com", "watcher2@example.com"]}'
        FILE_WRITTEN =>
            path: 'projects/timeline/emails/uuid1.json'
            contents: '{"raw_email": "RnJvbTogdXNlckBleGFtcGxlLmNvbQpUbzogdGltZWxpbmVAcHJvamVjdHMucmlja2FyZGxpbmRiZXJnLm1lCkNvbnRlbnQtVHlwZTogdGV4dC9wbGFpbjsgY2hhcnNldD0idXRmLTgiCkNvbnRlbnQtVHJhbnNmZXItRW5jb2Rpbmc6IDdiaXQKTUlNRS1WZXJzaW9uOiAxLjAKU3ViamVjdDogSGVsbG8gV29ybGQhCgpoZWxsbwo="}'
        FILE_WRITTEN =>
            path: 'projects/timeline/conversations/entries/uuid2.json'
            contents: '{"source_email": "uuid1"}'
        FILE_WRITTEN =>
            path: 'projects/timeline/conversations/uuid3.json'
            contents: '{"subject": "Hello World!", "entries": [{"id": "uuid2"}]}'
        FILE_WRITTEN =>
            path: 'projects/timeline/index.json'
            contents: '{"watchers": ["watcher1@example.com", "watcher2@example.com"], "conversations": [{"id": "uuid3"}]}'

        >>> database.project("timeline").load()["conversations"]
        [{'id': 'uuid3'}]

        >>> database.project("timeline").conversation("uuid3").load()
        {'subject': 'Hello World!', 'entries': [{'id': 'uuid2'}]}

        >>> base64.b64decode(
        ...     database.project("timeline").email(
        ...         database.project("timeline").conversation_entry("uuid2").load()["source_email"]
        ...     ).load()["raw_email"]
        ... ) == raw_email
        True

        If the project does not exists, I fail:

        >>> processor.process(Email.create_test_instance(
        ...     to_address="non_existing_project@projects.rickardlindberg.me"
        ... ).render())
        Traceback (most recent call last):
            ...
        projects.ProjectNotFound: non_existing_project
        """
        email = Email.parse(raw_email)
        project = email.get_user()
        if not self.db.project(project).exists():
            raise ProjectNotFound(project)
        conversation = self.db.project(project).create_conversation(email.get_subject(), raw_email)
        for watcher in self.db.project(project).load().get("watchers", []):
            notification = Email()
            notification.copy_plain_text_body_from(email)
            notification.set_subject(email.get_subject())
            notification.set_to(watcher)
            notification.set_from(f"{project}@projects.rickardlindberg.me")
            notification.set_reply_to(f"{project}+{conversation.id}@projects.rickardlindberg.me")
            notification.send(self.smtp_server)

class DatabaseEntity:

    def __init__(self, store, path, entity_id):
        self.store = store
        self.namespace = path
        self.id = entity_id

    def load(self):
        return self.store.load(self.namespace, self.id)

    def exists(self):
        return self.store.exists(self.namespace, self.id)

    def create(self, data):
        self.id = self.store.create(self.namespace, data, self.id)

class ProjectEntity(DatabaseEntity):

    def __init__(self, store, name):
        DatabaseEntity.__init__(self, store, f"projects/{name}", "index")
        self.name = name

    def create(self):
        DatabaseEntity.create(self, {})

    def create_conversation(self, subject, raw_email):
        conversation_id = self.store.create(
            f"projects/{self.name}/conversations/",
            {
                "subject": subject,
                "entries": [{
                    "id": self.store.create(
                        f"projects/{self.name}/conversations/entries/",
                        {
                            "source_email": self.email(None).create(raw_email).id
                        }
                    )
                }]
            }
        )
        self.store.append(
            self.namespace,
            self.id,
            "conversations",
            {"id": conversation_id}
        )
        return self.conversation(conversation_id)

    def add_watcher(self, email):
        self.store.append(self.namespace, self.id, "watchers", email)

    def conversation(self, conversation_id):
        return ConversationEntity(self.store, self.name, conversation_id)

    def conversation_entry(self, entry_id):
        return ConversationEntryEntity(self.store, self.name, entry_id)

    def email(self, email_id):
        return EmailEntity(self.store, self.name, email_id)

class ConversationEntity(DatabaseEntity):

    def __init__(self, store, project_name, conversation_id):
        DatabaseEntity.__init__(self, store,
            f"projects/{project_name}/conversations", conversation_id)

class ConversationEntryEntity(DatabaseEntity):

    def __init__(self, store, project_name, entry_id):
        DatabaseEntity.__init__(self, store,
            f"projects/{project_name}/conversations/entries", entry_id)

class EmailEntity(DatabaseEntity):

    def __init__(self, store, project_name, email_id):
        DatabaseEntity.__init__(self, store,
            f"projects/{project_name}/emails", email_id)

    def create(self, raw_email):
        DatabaseEntity.create(self, {
            "raw_email": base64.b64encode(raw_email).decode("ascii"),
        })
        return self

class Database:

    def __init__(self, store):
        self.store = store

    def project(self, name):
        return ProjectEntity(self.store, name)

class JsonStore:

    def __init__(self, filesystem, uuid):
        self.filesystem = filesystem
        self.uuid = uuid

    def exists(self, namespace, object_id):
        return self.filesystem.exists(self.path(namespace, object_id))

    def load(self, namespace, object_id):
        return json.loads(self.filesystem.read(self.path(namespace, object_id)))

    def append(self, namespace, object_id, key, item):
        x = self.load(namespace, object_id)
        if key not in x:
            x[key] = []
        x[key].append(item)
        self.filesystem.write(self.path(namespace, object_id), json.dumps(x))

    def create(self, namespace, data, object_id=None):
        if object_id is None:
            object_id = self.uuid.get()
        self.filesystem.write(
            self.path(namespace, object_id),
            json.dumps(data)
        )
        return object_id

    def path(self, path, object_id):
        return os.path.join(path, f"{object_id}.json")

class ProjectNotFound(ValueError):
    pass

class Email:

    @staticmethod
    def create_test_instance(
        from_address="user@example.com",
        to_address="to@example.com",
        body="hello",
        subject="subject"
    ):
        """
        >>> email = Email.create_test_instance()
        >>> email.get_from()
        'user@example.com'
        >>> email.get_to()
        'to@example.com'
        >>> email.get_plain_text_body()
        'hello\\n'
        >>> email.get_subject()
        'subject'
        """
        email = Email()
        email.set_from(from_address)
        email.set_to(to_address)
        email.set_plain_text_body(body)
        email.set_subject(subject)
        return email

    @staticmethod
    def parse(text):
        """
        >>> email = Email.parse(Email.create_test_instance(
        ...     from_address="test@example.com",
        ...     body="test",
        ...     subject="foo",
        ... ).render())
        >>> email.get_from()
        'test@example.com'
        >>> email.get_plain_text_body()
        'test\\n'
        >>> email.get_subject()
        'foo'
        """
        parser = email.parser.BytesParser(policy=email.policy.default)
        return Email(parser.parsebytes(text))

    def render(self):
        """
        Can render emails:

        >>> print(Email.create_test_instance().render().decode("ascii"))
        From: user@example.com
        To: to@example.com
        Content-Type: text/plain; charset="utf-8"
        Content-Transfer-Encoding: 7bit
        MIME-Version: 1.0
        Subject: subject
        <BLANKLINE>
        hello
        <BLANKLINE>
        """
        return self.email_message.as_bytes()

    def __init__(self, email_message=None):
        if email_message is None:
            self.email_message = email.message.EmailMessage()
        else:
            self.email_message = email_message

    def send(self, smtp_server):
        smtp_server.send(self.email_message)

    def get_user(self):
        """
        >>> Email.create_test_instance().get_user()
        'to'
        """
        return self.get_to().split("@", 1)[0]

    def get_subject(self):
        return self.email_message["Subject"]

    def set_subject(self, subject):
        self._set_header("Subject", subject)

    def get_from(self):
        return self.email_message["From"]

    def set_from(self, from_address):
        self._set_header("From", from_address)

    def get_to(self):
        return self.email_message["To"]

    def set_to(self, to_address):
        self._set_header("To", to_address)

    def set_reply_to(self, reply_to_address):
        self._set_header("Reply-To", reply_to_address)

    def get_plain_text_body(self):
        return self.email_message.get_content()

    def set_plain_text_body(self, body):
        self.email_message.set_content(body)

    def copy_plain_text_body_from(self, email):
        """
        >>> source = Email.create_test_instance(body="body")
        >>> target = Email()
        >>> target.copy_plain_text_body_from(source)
        >>> target.get_plain_text_body()
        'body\\n'

        >>> source = Email()
        >>> target = Email()
        >>> target.copy_plain_text_body_from(source)
        >>> target.get_plain_text_body()
        '<no plain body found>\\n'
        """
        plain_body_part = email.email_message.get_body(["plain"])
        if plain_body_part:
            plain_body = plain_body_part.get_content()
        else:
            plain_body = "<no plain body found>"
        self.email_message.set_content(plain_body)

    def _set_header(self, name, value):
        del self.email_message[name]
        self.email_message[name] = value

class Observable:

    def __init__(self):
        self.listeners = []

    def add_listener(self, listener):
        self.listeners.append(listener)

    def notify(self, name, event):
        for listener in self.listeners:
            listener.notify(name, event)

    def track_events(self):
        events = Events()
        self.add_listener(events)
        return events

class Events:

    def __init__(self):
        self.events = []

    def notify(self, name, data):
        self.events.append((name, data))

    def track(self, observable):
        observable.add_listener(self)
        return observable

    def filter(self, filter_name):
        events = Events()
        for name, data in self.events:
            if name == filter_name:
                events.notify(name, data)
        return events

    def __repr__(self):
        def format_event(name, data):
            part = []
            for key, value in data.items():
                if key != "type":
                    part.append(f"\n    {key}: {repr(value)}")
            return f"{name} =>{''.join(part)}"
        return "\n".join(format_event(name, data) for name, data in self.events)

class SMTPServer(Observable):

    """
    I am an infrastructure wrapper for an SMPT server.

    >>> smtp_server = SMTPServer.create_null()
    >>> events = smtp_server.track_events()
    >>> Email.create_test_instance().send(smtp_server)
    >>> events
    EMAIL_SENT =>
        from: 'user@example.com'
        to: 'to@example.com'
        reply-to: None
        subject: 'subject'
        body: 'hello\\n'

    >>> isinstance(SMTPServer.create(), SMTPServer)
    True
    """

    @staticmethod
    def create():
        return SMTPServer(smtplib=smtplib)

    @staticmethod
    def create_null():
        class NullSMTP:
            def send_message(self, message):
                pass
        class NullSmtplib:
            @contextlib.contextmanager
            def SMTP(self, host):
                yield NullSMTP()
        return SMTPServer(smtplib=NullSmtplib())

    def __init__(self, smtplib):
        Observable.__init__(self)
        self.smtplib = smtplib

    def send(self, email):
        with self.smtplib.SMTP(host="localhost") as smtp:
            smtp.send_message(email)
            self.notify("EMAIL_SENT", {
                "from": email["From"],
                "to": email["To"],
                "reply-to": email["Reply-To"],
                "subject": email["Subject"],
                "body": email.get_content(),
            })

class UUID:

    """
    I am an infrastructure wrapper for UUIDs.

    >>> uuid = UUID.create().get()
    >>> type(uuid)
    <class 'str'>
    >>> len(uuid)
    32

    The null version of me returns predictable ids:

    >>> uuid = UUID.create_null()
    >>> uuid.get()
    'uuid1'
    >>> uuid.get()
    'uuid2'
    """

    @staticmethod
    def create():
        return UUID(uuid=uuid)

    @staticmethod
    def create_null():
        class NullUuid4:
            def __init__(self, number):
                self.hex = f"uuid{number}"
        class NullUuid:
            counter = 0
            def uuid4(self):
                self.counter += 1
                return NullUuid4(self.counter)
        return UUID(uuid=NullUuid())

    def __init__(self, uuid):
        self.uuid = uuid

    def get(self):
        return self.uuid.uuid4().hex

class Filesystem(Observable):

    """
    I am an infrastructure wrapper for working with the filesystem.
    """

    @staticmethod
    def create():
        return Filesystem(os=os, builtins=builtins)

    @staticmethod
    def create_null():
        in_memory_store = {}
        class NullPath:
            def exists(self, path):
                return path in in_memory_store
        class NullOs:
            path = NullPath()
            def makedirs(self, path):
                pass
        class NullBuiltins:
            @contextlib.contextmanager
            def open(self, path, mode):
                if mode == "r":
                    yield NullFileRead(path)
                elif mode == "w":
                    yield NullFileWrite(path)
                else:
                    raise ValueError(f"Invalid mode {mode}")
        class NullFile:
            def __init__(self, path):
                self.path = path
        class NullFileRead(NullFile):
            def read(self):
                return in_memory_store[self.path]
        class NullFileWrite(NullFile):
            def write(self, contents):
                in_memory_store[self.path] = contents
        return Filesystem(os=NullOs(), builtins=NullBuiltins())

    def __init__(self, os, builtins):
        Observable.__init__(self)
        self.os = os
        self.builtins = builtins

    def exists(self, path):
        """
        Exists in real world:

        >>> filesystem = Filesystem.create()

        >>> filesystem.exists("README.md")
        True

        >>> filesystem.exists("non_existing_file")
        False

        Exists in null version:

        >>> filesystem = Filesystem.create_null()
        >>> filesystem.exists("non_existing_file")
        False
        >>> filesystem.write("non_existing_file", "")
        >>> filesystem.exists("non_existing_file")
        True
        """
        return self.os.path.exists(path)

    def read(self, path):
        """
        >>> tmp_dir = tempfile.TemporaryDirectory()
        >>> tmp_path = os.path.join(tmp_dir.name, "test")
        >>> filesystem = Filesystem.create()

        >>> _ = open(tmp_path, "w").write("test content")
        >>> filesystem.read(tmp_path)
        'test content'
        """
        with self.builtins.open(path, "r") as f:
            return f.read()

    def write(self, path, contents):
        """
        >>> tmp_dir = tempfile.TemporaryDirectory()
        >>> tmp_path = os.path.join(tmp_dir.name, "subdir1", "subdir2", "test")
        >>> filesystem = Filesystem.create()

        >>> filesystem.write(tmp_path, "test content")
        >>> filesystem.write(tmp_path, "test content")
        >>> open(tmp_path).read()
        'test content'

        I log writes:

        >>> filesystem = Filesystem.create_null()
        >>> events = filesystem.track_events()
        >>> filesystem.write("foo", "contents")
        >>> events
        FILE_WRITTEN =>
            path: 'foo'
            contents: 'contents'
        """
        dir_path = os.path.dirname(path)
        if not self.exists(dir_path):
            self.os.makedirs(dir_path)
        with self.builtins.open(path, "w") as f:
            f.write(contents)
        self.notify("FILE_WRITTEN", {"path": path, "contents": contents})

class Stdin:

    """
    I am an infrastructure wrapper for reading stdin:

    >>> print(subprocess.run([
    ...     "python", "-c",
    ...     "from projects import Stdin;"
    ...         "print(Stdin.create().read())",
    ... ], input="test", stdout=subprocess.PIPE, text=True).stdout.strip())
    b'test'

    I can configure what stdin is:

    >>> Stdin.create_null(b"configured response").read()
    b'configured response'
    """

    @staticmethod
    def create():
        return Stdin(sys=sys)

    @staticmethod
    def create_null(response):
        assert isinstance(response, bytes)
        class NullBuffer:
            def read(self):
                return response
        class NullStdin:
            buffer = NullBuffer()
        class NullSys:
            stdin = NullStdin()
        return Stdin(sys=NullSys())

    def __init__(self, sys):
        self.sys = sys

    def read(self):
        return self.sys.stdin.buffer.read()

class Args:

    """
    I am an infrastructure wrapper for reading program arguments (via the sys
    module).

    I return the arguments passed to the program:

    >>> print(subprocess.run([
    ...     "python", "-c",
    ...     "from projects import Args;"
    ...         "print(Args.create().get())",
    ...     "arg1", "arg2"
    ... ], stdout=subprocess.PIPE, text=True).stdout.strip())
    ['arg1', 'arg2']

    The null version of me does not read arguments passed to the program, but
    instead returns configured arguments:

    >>> print(subprocess.run([
    ...     "python", "-c",
    ...     "from projects import Args;"
    ...         "print(Args.create_null(['configured']).get())",
    ...     "arg1", "arg2"
    ... ], stdout=subprocess.PIPE, text=True).stdout.strip())
    ['configured']
    """

    def __init__(self, sys):
        self.sys = sys

    def get(self):
        return self.sys.argv[1:]

    @staticmethod
    def create():
        return Args(sys=sys)

    @staticmethod
    def create_null(args):
        class NullSys:
            argv = [None]+args
        return Args(NullSys())

if __name__ == "__main__":
    ProjectsApp.create().run()
