#!/usr/bin/env python3

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
    >>> ProjectsApp.create().run()
    Projects!
    """

    @staticmethod
    def create():
        return ProjectsApp()

    def run(self):
        print("Projects!")

if __name__ == "__main__":
    ProjectsApp.create().run()
