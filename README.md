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
    incoming emails --> | code hosting platform | -> outgoing emails
                        |                       |
                        +-----------------------+
```
