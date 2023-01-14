#!/usr/bin/env python3

import subprocess
import sys
from email.message import EmailMessage
from email.parser import Parser
from email.policy import default

"""
>>> 1+1
2

* give system an email
* assert that conversation is created
* assert that email updates are sent

cat email | ./projects.py process_email
"""

class ProjectsApp:

    """
    I can process an email:

    >>> ProjectsApp.run_in_test_mode(
    ...     args=["process_email"],
    ...     stdin=Email.create_test_instance(from_address="timeline@projects.rickardlindberg.me").render()
    ... )
    Projects!

    I fail if command is unknown:

    >>> ProjectsApp.run_in_test_mode(
    ...     args=["unknown_command"],
    ... )
    Traceback (most recent call last):
        ...
    SystemExit: Unknown command ['unknown_command']

    I can instantiate myself:

    >>> isinstance(ProjectsApp.create(), ProjectsApp)
    True
    """

    @staticmethod
    def create():
        return ProjectsApp(
            args=Args.create()
        )

    @staticmethod
    def run_in_test_mode(args=[], stdin=""):
        app = ProjectsApp(
            args=Args.create_null(args)
        )
        return app.run()

    def __init__(self, args):
        self.args = args

    def run(self):
        if self.args.get() == ["process_email"]:
            print("Projects!")
        else:
            sys.exit(f"Unknown command {self.args.get()}")

class Email:

    @staticmethod
    def create_test_instance(
        from_address="user@example.com",
        body="hello"
    ):
        email = Email()
        email.set_from(from_address)
        email.set_body(body)
        return email

    @staticmethod
    def parse(text):
        """
        >>> email = Email.parse(Email.create_test_instance().render())
        >>> email.get_from()
        'user@example.com'
        >>> email.get_body()
        'hello\\n'
        """
        return Email(Parser(policy=default).parsestr(text))

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
        return str(self.email)

    def __init__(self, email_message=None):
        self.email = EmailMessage() if email_message is None else email_message

    def get_from(self):
        return self.email["From"]

    def set_from(self, from_address):
        self.email["From"] = from_address

    def get_body(self):
        return self.email.get_content()

    def set_body(self, body):
        self.email.set_content(body)

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
