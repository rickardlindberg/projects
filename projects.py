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

    >>> filesystem = ProjectsApp.run_in_test_mode(
    ...     args=["process_email"],
    ...     stdin=Email.create_test_instance(
    ...         from_address="timeline@projects.rickardlindberg.me"
    ...     ).render(),
    ...     filesystem={
    ...         Database.get_project_path("timeline"): "{}",
    ...     }
    ... )
    >>> len(json.loads(filesystem.read("projects/timeline.json"))["conversations"])
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
            filesystem=Filesystem.create(),
            uuid=UUID.create(),
        )

    @staticmethod
    def run_in_test_mode(args=[], stdin="", filesystem={}):
        fs_wrapper = Filesystem.create_null()
        for path, contents in filesystem.items():
            fs_wrapper.write(path, contents)
        app = ProjectsApp(
            args=Args.create_null(args),
            stdin=Stdin.create_null(stdin),
            filesystem=fs_wrapper,
            uuid=UUID.create_null(),
        )
        app.run()
        return fs_wrapper

    def __init__(self, args, stdin, filesystem, uuid):
        self.args = args
        self.stdin = stdin
        self.filesystem = filesystem
        self.uuid = uuid

    def run(self):
        if self.args.get() == ["process_email"]:
            action = email_to_action(Email.parse(self.stdin.read()))
            return getattr(EmailProcessor(self.filesystem, self.uuid), action["name"])(**action["args"])
        else:
            sys.exit(f"Unknown command {self.args.get()}")

class EmailProcessor:

    @staticmethod
    def create_test_instance():
        filesystem = Filesystem.create_null()
        processor = EmailProcessor(filesystem, uuid=UUID.create_null())
        return filesystem, processor

    def __init__(self, filesystem, uuid):
        self.filesystem = filesystem
        self.uuid = uuid
        self.db = Database(self.filesystem, self.uuid)

    def project_new_conversation(self, project):
        """
        I create a new conversation in a project:

        >>> filesystem, processor = EmailProcessor.create_test_instance()
        >>> filesystem.write("projects/user.json", "{}")
        >>> processor.project_new_conversation("user")
        >>> filesystem.read("projects/user.json")
        '{"conversations": [{"id": "uuid1"}]}'
        >>> filesystem.read("projects/user/conversations/uuid1.json")
        '{"subject": "foo"}'

        If the project does not exists, I fail:

        >>> processor.project_new_conversation("non_existing_project")
        Traceback (most recent call last):
            ...
        projects.ProjectNotFound: non_existing_project
        """
        if not self.db.project_exists(project):
            raise ProjectNotFound(project)
        self.db.create_conversation(project)

def email_to_action(email):
    """
    >>> email_to_action(Email.create_test_instance(
    ...     from_address="test@projects.rickardlindberg.me"
    ... ))
    {'name': 'project_new_conversation', 'args': {'project': 'test'}}
    """
    return {
        "name": "project_new_conversation",
        "args": {
            "project": email.get_user(),
        },
    }

class Database:

    def __init__(self, filesystem, uuid):
        self.filesystem = filesystem
        self.uuid = uuid

    @staticmethod
    def get_project_path(name):
        return f"projects/{name}.json"

    @staticmethod
    def get_conversations_path(project_name):
        return f"projects/{project_name}/conversations/"

    def project_exists(self, name):
        return self.filesystem.exists(self.get_project_path(name))

    def create_conversation(self, project):
        store = JsonStore(self.filesystem, self.uuid)
        conversation_id = store.create(
            self.get_conversations_path(project),
            {"subject": "foo"}
        )
        store.append(
            self.get_project_path(project),
            "conversations",
            {"id": conversation_id}
        )

class JsonStore:

    def __init__(self, filesystem, uuid):
        self.filesystem = filesystem
        self.uuid = uuid

    def read(self, path):
        return json.loads(self.filesystem.read(path))

    def append(self, path, key, item):
        x = self.read(path)
        if key not in x:
            x[key] = []
        x[key].append(item)
        self.filesystem.write(path, json.dumps(x))

    def create(self, path, data):
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
        body="hello"
    ):
        """
        >>> email = Email.create_test_instance()
        >>> email.get_from()
        'user@example.com'
        >>> email.get_body()
        'hello\\n'
        """
        email = Email()
        email.set_from(from_address)
        email.set_body(body)
        return email

    @staticmethod
    def parse(text):
        """
        >>> email = Email.parse(Email.create_test_instance(
        ...     from_address="test@example.com",
        ...     body="test",
        ... ).render())
        >>> email.get_from()
        'test@example.com'
        >>> email.get_body()
        'test\\n'
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
