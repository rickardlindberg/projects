# Projects

This is an attempt to build my ideal code hosting platform.

## Initial story

1. User sends email to `timeline@projects.rickardlindberg.me`

2. Email is processed by the system and a new **conversation** is created.

3. Everyone that **watches** the `timeline` **project** is sent an email update
   about the conversation.

    * The email has `Reply-To` set to
      `timeline+<id>@projects.rickardlindberg.me`.

4. A watcher receiving the update replies to it.

5. The reply is processed by the system and is added to the conversation.

6. Everyone that watches the conversation `timeline+<id>` is sent an email
   update about the reply in the conversation.

```
                    +-----------------------+
                    |                       |
incoming emails --> | code hosting platform | --> outgoing emails
                    |                       |
                    +-----------------------+
                               | ^
                               | |
                               V |
                    +-----------------------+
                    |       database        |
                    |                       |
                    | * projects            |
                    | * conversations       |
                    +-----------------------+
```

Limitations:

* No web UI
* Just a new kind of mailing list
* Incoming emails can be added manually
* Projects can be created manually
* Watchers can be added manually

## Notes on sending emails

Sending emails is tricky. Or rather, it is tricky to get email servers to trust
the emails you send and not treat it as spam.

Here are some notes on how to improve your credebility.

### Reverse DNS

From [Best practices for SMTP servers](https://www.fastmail.help/hc/en-us/articles/1500000278362-Best-practices-for-SMTP-servers):

> Forward and reverse DNS must match

> HELO string must match reverse DNS

In `linode/setup_fedora_linode.sh` I setup the hostname to be the fully
qualified domain name.

I belive postfix uses that in the `HELO` string.

Reverse DNS for a Linode can be configured in their user interface.
