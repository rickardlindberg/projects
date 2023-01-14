#!/usr/bin/env python3

import email.message
import email.parser
import email.policy
import subprocess
import sys

class ProjectsApp:

    """
    Email processing
    ================

    I can process emails:

    >>> ProjectsApp.run_in_test_mode(
    ...     args=["process_email"],
    ...     stdin=Email.create_test_instance(
    ...         from_address="timeline@projects.rickardlindberg.me"
    ...     ).render()
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
            stdin=Stdin.create()
        )

    @staticmethod
    def run_in_test_mode(args=[], stdin=""):
        app = ProjectsApp(
            args=Args.create_null(args),
            stdin=Stdin.create_null(stdin)
        )
        return app.run()

    def __init__(self, args, stdin):
        self.args = args
        self.stdin = stdin

    def run(self):
        if self.args.get() == ["process_email"]:
            EmailProcessor().process(Email.parse(self.stdin.read()))
        else:
            sys.exit(f"Unknown command {self.args.get()}")

class EmailProcessor:

    """
    I create a conversation when I receive an email to a project address:

    >>> EmailProcessor().process(Email.create_test_instance())
    Conversation created
    """

    def process(self, email):
        print("Conversation created")

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

    def get_from(self):
        return self.email_message["From"]

    def set_from(self, from_address):
        self.email_message["From"] = from_address

    def get_body(self):
        return self.email_message.get_content()

    def set_body(self, body):
        self.email_message.set_content(body)

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
