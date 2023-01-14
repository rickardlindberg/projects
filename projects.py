#!/usr/bin/env python3

import builtins
import contextlib
import email.message
import email.parser
import email.policy
import os
import subprocess
import sys
import tempfile

class ProjectsApp:

    """
    Email processing
    ================

    I can process emails:

    >>> ProjectsApp.run_in_test_mode(
    ...     args=["process_email"],
    ...     stdin=Email.create_test_instance(
    ...         from_address="timeline@projects.rickardlindberg.me"
    ...     ).render(),
    ...     fs={
    ...         Database.get_project_path("timeline"): "{}",
    ...     }
    ... )
    Conversation created

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
            filesystem=Filesystem.create()
        )

    @staticmethod
    def run_in_test_mode(args=[], stdin="", fs={}):
        fs_wrapper = Filesystem.create_null()
        for path, contents in fs.items():
            fs_wrapper.write(path, contents)
        app = ProjectsApp(
            args=Args.create_null(args),
            stdin=Stdin.create_null(stdin),
            filesystem=fs_wrapper
        )
        return app.run()

    def __init__(self, args, stdin, filesystem):
        self.args = args
        self.stdin = stdin
        self.filesystem = filesystem

    def run(self):
        if self.args.get() == ["process_email"]:
            EmailProcessor(self.filesystem).process(Email.parse(self.stdin.read()))
        else:
            sys.exit(f"Unknown command {self.args.get()}")

class EmailProcessor:

    """
    I create a conversation when I receive an email to a project address:

    >>> fs, processor = EmailProcessor.create_test_instance()

    Given a project 'test':

    >>> fs.write("projects/user.json", "{}")

    >>> processor.process(Email.create_test_instance())
    Conversation created

    If a receive an email to the project address that does not exist, I fail:

    >>> processor.process(Email.create_test_instance(from_address="non_existing_project@projects.rickardlindberg.me"))
    Traceback (most recent call last):
        ...
    projects.ConversationNotFound: non_existing_project
    """

    @staticmethod
    def create_test_instance():
        fs = Filesystem.create_null()
        processor = EmailProcessor(fs)
        return fs, processor

    def __init__(self, filesystem):
        self.filesystem = filesystem
        self.db = Database(self.filesystem)

    def process(self, email):
        if not self.db.project_exists(email.get_user()):
            raise ConversationNotFound(f"{email.get_user()}")
        print("Conversation created")

class Database:

    def __init__(self, filesystem):
        self.filesystem = filesystem

    @staticmethod
    def get_project_path(name):
        return f"projects/{name}.json"

    def project_exists(self, name):
        return self.filesystem.exists(self.get_project_path(name))

class ConversationNotFound(ValueError):
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

class Filesystem:

    """
    I am an infrastructure wrapper for working with the filesystem.
    """

    @staticmethod
    def create():
        return Filesystem(os=os, builtins=builtins)

    @staticmethod
    def create_null():
        fs = {}
        class NullPath:
            def exists(self, path):
                return path in fs
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
                return fs[self.path]
        class NullFileWrite(NullFile):
            def write(self, contents):
                fs[self.path] = contents
        return Filesystem(os=NullOs(), builtins=NullBuiltins())

    def __init__(self, os, builtins):
        self.os = os
        self.builtins = builtins

    def exists(self, path):
        """
        Exists in real world:

        >>> fs = Filesystem.create()

        >>> fs.exists("README.md")
        True

        >>> fs.exists("non_existing_file")
        False

        Exists in null version:

        >>> fs = Filesystem.create_null()
        >>> fs.exists("non_existing_file")
        False
        >>> fs.write("non_existing_file", "")
        >>> fs.exists("non_existing_file")
        True
        """
        return self.os.path.exists(path)

    def read(self, path):
        """
        >>> tmp_dir = tempfile.TemporaryDirectory()
        >>> tmp_path = os.path.join(tmp_dir.name, "test")
        >>> fs = Filesystem.create()

        >>> _ = open(tmp_path, "w").write("test content")
        >>> fs.read(tmp_path)
        'test content'
        """
        with self.builtins.open(path, "r") as f:
            return f.read()

    def write(self, path, contents):
        """
        >>> tmp_dir = tempfile.TemporaryDirectory()
        >>> tmp_path = os.path.join(tmp_dir.name, "test")
        >>> fs = Filesystem.create()

        >>> fs.write(tmp_path, "test content")
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
