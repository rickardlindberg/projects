#!/usr/bin/env python3

import builtins
import contextlib
import email.message
import email.parser
import email.policy
import json
import os
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
    ...         from_address="timeline@projects.rickardlindberg.me"
    ...     ).render(),
    ...     database_inits=[
    ...         lambda db: db.create_project("timeline"),
    ...     ]
    ... )

    >>> len(database.get_project("timeline")["conversations"])
    1

    NOTE: We just want to assert that the email was processed somehow. Details
    of email processing is implemented and tested in EmailProcessor.

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
            database=Database(
                filesystem=Filesystem.create(),
                uuid=UUID.create(),
            )
        )

    @staticmethod
    def run_in_test_mode(args=[], stdin="", database_inits=[]):
        database = Database(
            filesystem=Filesystem.create_null(),
            uuid=UUID.create_null()
        )
        for x in database_inits:
            x(database)
        app = ProjectsApp(
            args=Args.create_null(args),
            stdin=Stdin.create_null(stdin),
            database=database
        )
        app.run()
        return database

    def __init__(self, args, stdin, database):
        self.args = args
        self.stdin = stdin
        self.database = database

    def run(self):
        if self.args.get() == ["process_email"]:
            return EmailProcessor(self.database).process(self.stdin.read())
        else:
            sys.exit(f"Unknown command {self.args.get()}")

class EmailProcessor:

    @staticmethod
    def create_test_instance():
        database = Database(
            filesystem=Filesystem.create_null(),
            uuid=UUID.create_null()
        )
        processor = EmailProcessor(database)
        return database, processor

    def __init__(self, database):
        self.db = database

    def process(self, raw_email):
        """
        I create a new conversation in a project:

        >>> database, processor = EmailProcessor.create_test_instance()
        >>> database.create_project("timeline")
        >>> database.watch_project("timeline", "watcher1@example.com")
        >>> database.watch_project("timeline", "watcher2@example.com")

        >>> raw_email = Email.create_test_instance(
        ...     from_address="timeline@projects.rickardlindberg.me",
        ...     subject="Hello World!",
        ... ).render()
        >>> processor.process(raw_email)
        watcher1@example.com
        watcher2@example.com

        >>> database.get_project("timeline")["conversations"]
        [{'id': 'uuid2'}]

        >>> database.get_conversation("timeline", "uuid2")
        {'subject': 'Hello World!', 'entries': [{'id': 'uuid1'}]}

        >>> database.get_conversation_entry("timeline", "uuid1")["source_email"] == raw_email
        True

        If the project does not exists, I fail:

        >>> processor.process(Email.create_test_instance(
        ...     from_address="non_existing_project@projects.rickardlindberg.me"
        ... ).render())
        Traceback (most recent call last):
            ...
        projects.ProjectNotFound: non_existing_project
        """
        email = Email.parse(raw_email)
        project = email.get_user()
        if not self.db.project_exists(project):
            raise ProjectNotFound(project)
        self.db.create_conversation(project, email.get_subject(), raw_email)
        for watcher in self.db.get_project_watchers(project):
            print(watcher)

class Database:

    def __init__(self, filesystem, uuid):
        self.filesystem = filesystem
        self.store = JsonStore(filesystem, uuid)

    def get_project(self, name):
        return self.store.load(f"projects/{name}.json")

    def create_project(self, name):
        self.filesystem.write(f"projects/{name}.json", "{}")

    def project_exists(self, name):
        return self.filesystem.exists(f"projects/{name}.json")

    def watch_project(self, name, email):
        self.store.append(f"projects/{name}.json", "watchers", email)

    def get_project_watchers(self, name):
        return self.store.load(f"projects/{name}.json").get("watchers", [])

    def get_conversation(self, name, conversation_id):
        return self.store.load(f"projects/{name}/conversations/{conversation_id}.json")

    def create_conversation(self, project, subject, raw_email):
        conversation_id = self.store.create(
            f"projects/{project}/conversations/",
            {
                "subject": subject,
                "entries": [{
                    "id": self.store.create(
                        f"projects/{project}/conversations/entries/",
                        {
                            "source_email": raw_email,
                        }
                    )
                }]
            }
        )
        self.store.append(
            f"projects/{project}.json",
            "conversations",
            {"id": conversation_id}
        )

    def get_conversation_entry(self, project_name, entry_id):
        return self.store.load(f"projects/{project_name}/conversations/entries/{entry_id}.json")

class JsonStore:

    def __init__(self, filesystem, uuid):
        self.filesystem = filesystem
        self.uuid = uuid

    def load(self, path):
        return json.loads(self.filesystem.read(path))

    def append(self, path, key, item):
        x = self.load(path)
        if key not in x:
            x[key] = []
        x[key].append(item)
        self.filesystem.write(path, json.dumps(x))

    def create(self, path, data, object_id=None):
        if object_id is None:
            object_id = self.uuid.get()
        self.filesystem.write(
            os.path.join(path, f"{object_id}.json"),
            json.dumps(data)
        )
        return object_id

class ProjectNotFound(ValueError):
    pass

class Email:

    @staticmethod
    def create_test_instance(
        from_address="user@example.com",
        body="hello",
        subject="subject"
    ):
        """
        >>> email = Email.create_test_instance()
        >>> email.get_from()
        'user@example.com'
        >>> email.get_body()
        'hello\\n'
        >>> email.get_subject()
        'subject'
        """
        email = Email()
        email.set_from(from_address)
        email.set_body(body)
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
        >>> email.get_body()
        'test\\n'
        >>> email.get_subject()
        'foo'
        """
        return Email(email.parser.Parser(policy=email.policy.default).parsestr(text))

    def render(self):
        """
        Can render emails:

        >>> print(Email.create_test_instance().render())
        From: user@example.com
        Content-Type: text/plain; charset="utf-8"
        Content-Transfer-Encoding: 7bit
        MIME-Version: 1.0
        Subject: subject
        <BLANKLINE>
        hello
        <BLANKLINE>
        """
        return str(self.email_message)

    def __init__(self, email_message=None):
        if email_message is None:
            self.email_message = email.message.EmailMessage()
        else:
            self.email_message = email_message

    def get_user(self):
        """
        >>> Email.create_test_instance().get_user()
        'user'
        """
        return self.get_from().split("@", 1)[0]

    def get_subject(self):
        return self.email_message["Subject"]

    def set_subject(self, subject):
        self.email_message["Subject"] = subject

    def get_from(self):
        return self.email_message["From"]

    def set_from(self, from_address):
        self.email_message["From"] = from_address

    def get_body(self):
        return self.email_message.get_content()

    def set_body(self, body):
        self.email_message.set_content(body)

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

class Filesystem:

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
        >>> tmp_path = os.path.join(tmp_dir.name, "test")
        >>> filesystem = Filesystem.create()

        >>> filesystem.write(tmp_path, "test content")
        >>> open(tmp_path).read()
        'test content'
        """
        with self.builtins.open(path, "w") as f:
            f.write(contents)

class Stdin:

    """
    I am an infrastructure wrapper for reading stdin:

    >>> print(subprocess.run([
    ...     "python", "-c",
    ...     "from projects import Stdin;"
    ...         "print(Stdin.create().read())",
    ... ], input="test", stdout=subprocess.PIPE, text=True).stdout.strip())
    test

    I can configure what stdin is:

    >>> Stdin.create_null("configured response").read()
    'configured response'
    """

    @staticmethod
    def create():
        return Stdin(sys=sys)

    @staticmethod
    def create_null(response):
        class NullStdin:
            def read(self):
                return response
        class NullSys:
            stdin = NullStdin()
        return Stdin(sys=NullSys())

    def __init__(self, sys):
        self.sys = sys

    def read(self):
        return self.sys.stdin.read()

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
