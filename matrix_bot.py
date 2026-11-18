import asyncio
import json
import logging
import os
import queue
import threading
import time

import nio

import zwift_offline


logger = logging.getLogger('zoffline.matrix')


DEFAULT_HELP_MESSAGE = (
    'Commands: !online (riders online), !ping, !help. '
    'Other messages are relayed to riders in-game.'
)


class MatrixThread(threading.Thread):
    def __init__(self, config_file):
        threading.Thread.__init__(self, daemon=True)
        if not os.path.isfile(config_file):
            raise Exception("MatrixThread invoked without a configuration file")

        self.storage_dir = os.path.dirname(os.path.abspath(config_file))
        self.session_file = os.path.join(self.storage_dir, 'matrix-session.json')
        self.store_path = os.path.join(self.storage_dir, 'matrix-store')
        os.makedirs(self.store_path, exist_ok=True)

        (self.homeserver, self.user, self.password, self.room_id,
         self.announce, self.help_message) = self.read_config(config_file)

        self.client = None
        self.loop = None
        self.ready = False
        self.pending = queue.Queue()
        self.encryption_warning_shown = False
        self.presence_error_shown = False
        self.start()

    @staticmethod
    def read_config(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            lines = []
            for line in f:
                line = line.strip()
                # A Matrix room alias also starts with '#', so only treat
                # "# comment" (hash followed by a space) as a comment.
                if line and not line.startswith('# ') and not line.startswith(';'):
                    lines.append(line)

        if len(lines) < 4:
            raise Exception(
                "matrix.txt must contain at least: hostname, user, password, room_id"
            )

        homeserver, user, password, room_id = lines[:4]
        if not homeserver.startswith(('http://', 'https://')):
            homeserver = 'https://' + homeserver
        homeserver = homeserver.rstrip('/')

        options = {}
        for line in lines[4:]:
            if '=' in line:
                key, value = line.split('=', 1)
                options[key.strip().lower()] = value.strip()

        announce = options.get('announce_players', 'false').lower() in (
            '1', 'true', 'yes', 'on'
        )
        help_message = options.get('help_message') or DEFAULT_HELP_MESSAGE

        return homeserver, user, password, room_id, announce, help_message

    def load_session(self):
        if not os.path.isfile(self.session_file):
            return None
        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                session = json.load(f)
        except Exception as exc:
            print('MatrixThread: unable to read session file: %s' % repr(exc))
            return None

        if not isinstance(session, dict):
            return None
        if session.get('homeserver') != self.homeserver:
            return None
        if not session.get('user_id') or not session.get('device_id') or not session.get('access_token'):
            return None
        if not self.user_matches(session['user_id']):
            return None
        return session

    def user_matches(self, user_id):
        if self.user.startswith('@') and ':' in self.user:
            return self.user == user_id
        if '@' not in self.user:
            return user_id.split(':', 1)[0].lstrip('@') == self.user
        return True

    def save_session(self, response):
        session = {
            'homeserver': self.homeserver,
            'user_id': response.user_id,
            'device_id': response.device_id,
            'access_token': response.access_token,
        }
        tmp_file = self.session_file + '.tmp'
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(session, f, indent=2)
            os.replace(tmp_file, self.session_file)
            try:
                os.chmod(self.session_file, 0o600)
            except OSError:
                pass
        except Exception as exc:
            print('MatrixThread: unable to save session file: %s' % repr(exc))

    def clear_session(self):
        try:
            os.remove(self.session_file)
        except OSError:
            pass

    def new_client(self, device_id=''):
        config = nio.AsyncClientConfig(store_sync_tokens=True)
        return nio.AsyncClient(
            self.homeserver,
            self.user,
            device_id=device_id,
            store_path=self.store_path,
            config=config,
        )

    async def starter(self):
        self.ready = False
        session = self.load_session()
        if session:
            self.client = self.new_client(session['device_id'])
            self.client.restore_login(
                user_id=session['user_id'],
                device_id=session['device_id'],
                access_token=session['access_token'],
            )
            whoami = await self.client.whoami()
            if not isinstance(whoami, nio.WhoamiResponse):
                logger.warning(
                    'Matrix: stored session rejected (%s), logging in again',
                    getattr(whoami, 'message', repr(whoami)),
                )
                await self.client.close()
                self.client = None
                self.clear_session()
                session = None

        if not session:
            self.client = self.new_client()
            response = await self.client.login(
                self.password, device_name='zwift-offline'
            )
            if not isinstance(response, nio.LoginResponse):
                raise Exception(
                    'Matrix login failed: %s'
                    % getattr(response, 'message', repr(response))
                )
            self.save_session(response)

        try:
            await self.resolve_and_join()
            self.register_callbacks()
            self.client.add_response_callback(self.first_sync_callback, nio.SyncResponse)

            room = self.client.rooms.get(self.room_id)
            if room and room.encrypted and not self.client.olm:
                self.warn_encryption()

            await self.client.sync_forever(
                timeout=30000, full_state=True, set_presence='online'
            )
        finally:
            if self.client:
                try:
                    await self.client.close()
                except Exception:
                    pass
                self.client = None

    async def first_sync_callback(self, response):
        if not isinstance(response, nio.SyncResponse) or self.ready:
            return
        self.ready = True
        room = self.client.rooms.get(self.room_id) if self.client else None
        logger.info(
            'Matrix: initial sync complete; bridge ready (room %s %s)',
            self.room_id,
            'available' if room else 'NOT FOUND',
        )
        await self.flush_pending()

    async def flush_pending(self):
        while self.ready and self.client is not None:
            if self.room_id not in self.client.rooms:
                return
            try:
                text = self.pending.get_nowait()
            except queue.Empty:
                return
            await self.send_text(text)

    async def resolve_and_join(self):
        room_id = self.room_id
        if room_id.startswith('#'):
            response = await self.client.room_resolve_alias(room_id)
            if not isinstance(response, nio.RoomResolveAliasResponse):
                raise Exception(
                    'Unable to resolve Matrix room alias %s: %s'
                    % (room_id, getattr(response, 'message', repr(response)))
                )
            room_id = response.room_id

        response = await self.client.join(room_id)
        if isinstance(response, nio.JoinError):
            raise Exception(
                'Unable to join Matrix room %s: %s'
                % (room_id, response.message)
            )
        if isinstance(response, nio.JoinResponse):
            room_id = response.room_id
        self.room_id = room_id

    def register_callbacks(self):
        self.client.add_event_callback(self.message_callback, nio.RoomMessageText)
        self.client.add_event_callback(self.encrypted_callback, nio.MegolmEvent)
        self.client.add_event_callback(self.encrypted_callback, nio.UnknownEncryptedEvent)

    def warn_encryption(self):
        if not self.encryption_warning_shown:
            logger.warning(
                'Matrix: room is encrypted but a message could not be decrypted. '
                'Ensure matrix-nio[e2e] is installed and room keys are shared with this device.'
            )
            self.encryption_warning_shown = True

    async def message_callback(self, room, event):
        if not self.ready:
            return
        if room.room_id != self.room_id:
            return
        if event.sender == self.client.user_id:
            return
        if room.encrypted and not self.client.olm:
            self.warn_encryption()
            return

        body = event.body
        if not isinstance(body, str) or not body:
            return

        command = body.strip()
        logger.info('Matrix: received %r from %s', command, event.sender)
        if command == '!online':
            await self.send_text(str(len(getattr(zwift_offline, 'online', {}))) + ' riders online')
        elif command == '!ping':
            await self.send_text('pong')
        elif command == '!help':
            await self.send_text(self.help_message)
        elif not command.startswith('!'):
            try:
                sender = room.user_name(event.sender) or event.sender
            except Exception:
                sender = event.sender
            try:
                zwift_offline.send_message(body, sender)
            except Exception as exc:
                logger.warning('Matrix: unable to relay message in-game: %r', exc)

    async def encrypted_callback(self, room, event):
        if room.room_id == self.room_id:
            self.warn_encryption()

    async def send_text(self, text):
        if not self.ready or not self.client:
            self.pending.put(text)
            logger.warning('Matrix: queued outgoing message (not ready): %s', text)
            return
        if self.room_id not in self.client.rooms:
            self.pending.put(text)
            logger.warning('Matrix: room not synced yet; queued: %s', text)
            return
        room = self.client.rooms.get(self.room_id)
        if room and room.encrypted and not self.client.olm:
            self.warn_encryption()
            return
        try:
            response = await self.client.room_send(
                self.room_id,
                'm.room.message',
                {'msgtype': 'm.text', 'body': text},
                ignore_unverified_devices=True,
            )
            if isinstance(response, nio.RoomSendError):
                logger.warning('Matrix: send failed: %s', response.message)
            else:
                logger.info('Matrix: sent: %s', text)
        except Exception as exc:
            logger.exception('Matrix: send exception: %r', exc)

    async def set_presence(self, status_msg):
        if not self.client:
            return
        try:
            response = await self.client.set_presence('online', status_msg=status_msg)
            if isinstance(response, nio.PresenceSetError) and not self.presence_error_shown:
                print('MatrixThread: presence update failed: %s' % response.message)
                self.presence_error_shown = True
        except Exception as exc:
            if not self.presence_error_shown:
                print('MatrixThread: presence exception: %s' % repr(exc))
                self.presence_error_shown = True

    def submit(self, coroutine):
        if self.loop is None or self.client is None:
            coroutine.close()
            logger.warning('Matrix: skipped submit (loop/client not ready)')
            return
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
            future.add_done_callback(self.log_future_exception)
        except Exception as exc:
            coroutine.close()
            print('MatrixThread: unable to submit coroutine: %s' % repr(exc))

    @staticmethod
    def log_future_exception(future):
        try:
            future.result()
        except Exception as exc:
            print('MatrixThread: async exception: %s' % repr(exc))

    def send_message(self, message, sender_id=None):
        if sender_id is not None:
            try:
                profile = zwift_offline.get_partial_profile(sender_id)
                sender = profile.first_name + ' ' + profile.last_name
            except Exception:
                sender = 'Player'
            text = '%s: %s' % (sender, message)
        else:
            text = message
        if self.ready and self.loop is not None and self.client is not None:
            self.submit(self.send_text(text))
        else:
            self.pending.put(text)
            logger.info('Matrix: queued outgoing message: %s', text)

    def change_presence(self, n):
        if n > 0:
            status = '%s rider%s online' % (n, 's'[:n>1])
        else:
            status = 'No riders online'
        self.submit(self.set_presence(status))

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                self.loop.run_until_complete(self.starter())
            except Exception as exc:
                logger.exception('Matrix exception: %r', exc)
                if self.client:
                    try:
                        self.loop.run_until_complete(self.client.close())
                    except Exception:
                        pass
            self.client = None
            self.ready = False
            time.sleep(30)
