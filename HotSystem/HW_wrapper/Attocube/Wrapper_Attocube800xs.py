import json
import socket
from random import randint
from threading import Lock
from time import time, sleep
from ..Attocube import AttoException, AttoResult

class AttocubeDevice:
    TCP_PORT = 9090
    is_open = False
    request_id = randint(0, 1000000)
    request_id_lock = Lock()
    response_buffer = {}

    def __init__(self, address: str, simulation: bool = False):
        """
        Initialize and connect to the selected AMC device.

        :param address: The IP address of the device.
        """
        self.simulation = simulation
        self.bufferedSocket = None
        self.tcp = None
        self.address = address
        self.language = 0
        self.api_version = 2
        self.response_lock = Lock()

    def __del__(self):
        self.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def connect(self) -> None:
        """
        Connect to the device.
        """
        if not self.simulation and not self.is_open:
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp.settimeout(1) # Timeout in seconds
            tcp.connect((self.address, self.TCP_PORT))
            self.tcp = tcp
            self.bufferedSocket = tcp.makefile("rw", newline='\r\n')
            self.is_open = True
        else:
            self.is_open = True

    def close(self) -> None:
        """
        Close the connection to the device.
        """
        if not self.simulation and self.is_open:
            self.bufferedSocket.close()
            self.tcp.close()
            self.is_open = False
        else:
            self.is_open = False

    def send_request(self, method: str, params: list = None) -> int:
        """
        Send a JSON-RPC request to the device.

        :param method: The method name to call.
        :param params: The parameters to pass with the method call.
        :return: The request ID.
        """
        if self.simulation:
            return -1
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "api": self.api_version
        }
        if params:
            req["params"] = params
        with AttocubeDevice.request_id_lock:
            req["id"] = AttocubeDevice.request_id
            self.bufferedSocket.write(json.dumps(req))
            self.bufferedSocket.flush()
            AttocubeDevice.request_id += 1
            return req["id"]

    def get_response(self, request_id: int) -> AttoResult:
        """
        Get the response for a specific request ID.

        :param request_id: The request ID.
        :return: The response.
        """
        if self.simulation:
            print(f"{self.__class__.__name__}: Request ID {request_id}")
            return AttoResult({"result": [1, 2, 3]})
        start_time = time()
        while True:
            if request_id in self.response_buffer:
                response = self.response_buffer[request_id]
                del self.response_buffer[request_id]
                return response
            if time() - start_time > 1:
                raise TimeoutError("No result")

            if self.response_lock.acquire(blocking=False):
                try:
                    response = self.bufferedSocket.readline()
                    parsed = json.loads(response)
                    if parsed["id"] == request_id:
                        return AttoResult(parsed)
                    else:
                        self.response_buffer[parsed["id"]] = AttoResult(parsed)
                except OSError as e:
                    if "timed out" in str(e):
                        print(f"OSError: {e}")
                        self.close()
                        self.connect()
                    else:
                        raise e
                finally:
                    self.response_lock.release()
            else:
                sleep(0.01)

    def request(self, method: str, params: list = None) -> AttoResult:
        """
        Synchronously send a request and get the response.

        :param method: The method name to call.
        :param params: The parameters to pass with the method call.
        :return: The response.
        """
        if self.simulation:
            print(f"{self.__class__.__name__}: Sending {method} request with params {params}")
            return AttoResult({"result": [0, 1, 2]})
        if not self.is_open:
            raise AttoException("not connected, use connect()")
        request_id = self.send_request(method, params)
        try:
            response = self.get_response(request_id)
        except TimeoutError as e:
            print(f"Timeout: {e}")
            response = AttoResult({"result": [0, 1, 2]})
        return response

    @staticmethod
    def handle_error(response: AttoResult, ignore_function_error: bool = False, simulation: bool = False) -> int:
        """
        Handle an error in the response.

        :param response: The response to check for errors.
        :param ignore_function_error: Whether to ignore function-specific errors.
        :param simulation: Whether to run in simulation mode.
        :return: The error number.
        """
        if simulation:
            return 0
        err_no = response[0]
        if err_no != 0 and not ignore_function_error:
            raise AttoException("Error! " + str(err_no), err_no)
        return err_no
