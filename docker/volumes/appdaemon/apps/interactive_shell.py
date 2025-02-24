import appdaemon.plugins.hass.hassapi as hass
import threading
import socket
import traceback
import sys
from io import StringIO
import contextlib


class InteractiveShell(hass.Hass):
    def initialize(self):
        self.log("Interactive shell initializing")
        self.port = 8888  # You can change this port

        # Create a persistent globals dictionary to maintain state between commands
        self.shell_globals = {"self": self}
        self.shell_locals = {}

        # Start the shell server in a background thread
        threading.Thread(target=self.run_shell_server, daemon=True).start()
        self.log(f"Interactive shell ready! Connect with: nc localhost {self.port}")

    def run_shell_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind(('0.0.0.0', self.port))
            server.listen(1)

            while True:
                client, addr = server.accept()
                self.log(f"New connection from {addr}")
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client, addr),
                    daemon=True
                )
                client_thread.start()

        except Exception as e:
            self.log(f"Shell server error: {e}")
        finally:
            server.close()

    def handle_client(self, client, addr):
        try:
            # Welcome message
            client.send(b"AppDaemon Interactive Shell\n")
            client.send(b"Type Python code and press Enter to execute.\n")
            client.send(b"- Multi-line input is supported (finish with a blank line)\n")
            client.send(b"- Imports and variables persist across commands\n")
            client.send(b"- Type 'exit()' to disconnect\n")
            client.send(b"- Type 'help()' for more information\n\n>>> ")

            buffer = ""
            multi_line_mode = False
            multi_line_buffer = []

            while True:
                data = client.recv(1024)
                if not data:
                    break

                buffer += data.decode('utf-8')

                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.rstrip()

                    # Handle special commands
                    if line.lower() == 'exit()':
                        client.send(b"Goodbye!\n")
                        return

                    if line.lower() == 'help()':
                        self.send_help(client)
                        client.send(b">>> ")
                        continue

                    # Check for multi-line input
                    if not multi_line_mode and (line.endswith(':') or line.startswith('@')):
                        multi_line_mode = True
                        multi_line_buffer = [line]
                        client.send(b"... ")
                        continue

                    if multi_line_mode:
                        if line.strip() == "":
                            # End of multi-line input
                            command = "\n".join(multi_line_buffer)
                            multi_line_mode = False
                            multi_line_buffer = []

                            self.execute_command(command, client)
                            client.send(b">>> ")
                        else:
                            multi_line_buffer.append(line)
                            client.send(b"... ")
                    else:
                        # Single line mode
                        if line.strip():  # Only execute non-empty lines
                            self.execute_command(line, client)
                        client.send(b">>> ")

        except Exception as e:
            self.log(f"Error handling client {addr}: {e}")
            traceback.print_exc()
        finally:
            client.close()
            self.log(f"Connection closed for {addr}")

    @contextlib.contextmanager
    def capture_output(self):
        """Capture stdout and stderr"""
        new_out, new_err = StringIO(), StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = new_out, new_err
            yield new_out, new_err
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def execute_command(self, command, client):
        # Capture stdout and stderr during execution
        with self.capture_output() as (out, err):
            try:
                # First try to evaluate as an expression
                try:
                    result = eval(command, self.shell_globals, self.shell_locals)
                    if result is not None:
                        print(result)  # This will be captured in 'out'
                except SyntaxError:
                    # If it's not an expression, execute it as a statement
                    exec(command, self.shell_globals, self.shell_locals)
            except Exception as e:
                print(f"Error: {traceback.format_exc()}", file=sys.stderr)  # This will be captured in 'err'

        # Send captured stdout to client
        stdout_content = out.getvalue()
        if stdout_content:
            client.send(stdout_content.encode('utf-8'))

        # Send captured stderr to client
        stderr_content = err.getvalue()
        if stderr_content:
            client.send(stderr_content.encode('utf-8'))

    def send_help(self, client):
        help_text = """
AppDaemon Interactive Shell Help:
--------------------------------
- Variables and imports persist between commands
- Access the app instance via 'self'
- Special commands:
  * exit() - Disconnect from the shell
  * help() - Show this help message

Examples:
  >>> import datetime
  >>> datetime.datetime.now()
  >>> entities = self.get_state()  # Get all entity states
  >>> self.listen_state(my_callback, "light.living_room")  # Create a listener

Note: You can define functions with multi-line input:
  >>> def test_function():
  ...     return "It works!"
  ... 
  >>> test_function()

Home Assistant specific:
  >>> self.get_state("light.living_room")  # Get state of an entity
  >>> self.turn_on("switch.kitchen")  # Turn on a switch
  >>> self.call_service("light/turn_on", entity_id="light.bedroom", brightness=128)
"""
        client.send(help_text.encode('utf-8'))