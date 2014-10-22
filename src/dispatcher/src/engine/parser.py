# coding=utf-8
import base64

empty_byte_array = bytearray()


class Parser(object):
    """
    The parser which encode and decode engine packet
    """

    # Current protocol version
    protocol = 3

    # Packet type
    packet_types = {
        "open": 0,
        "close": 1,
        "ping": 2,
        "pong": 3,
        "message": 4,
        "upgrade": 5,
        "noop": 6,
    }

    packet_type_lists = (
        "open",
        "close",
        "ping",
        "pong",
        "message",
        "upgrade",
        "noop"
    )

    # Parser error packet
    error_packet = {
        "type": "error",
        "data": "parser error"
    }

    @staticmethod
    def encode_packet(packet, supports_binary=True, utf8_encoding=True):
        data = packet.get("data", None)

        type_buffer = str(Parser.packet_types[packet['type']])

        if data:
            if type(data) == bytearray:
                if not supports_binary:
                    return Parser.encode_base64_packet(packet)

                return type_buffer + data

            # Now we have a string or something, convert it to string first
            data = str(data)
            if utf8_encoding:
                data = data.encode("utf-8")

            return str(type_buffer) + data
        else:
            return str(type_buffer)

    @staticmethod
    def encode_base64_packet(packet):
        """
        Encode the packet to a base64 string
        :param packet:
        :return: The base64 string
        """
        data = packet["data"]
        if hasattr(data, "buffer"):
            data = data.buffer

        return 'b' + str(Parser.packet_types[packet["type"]]) + base64.standard_b64encode(data)

    @staticmethod
    def decode_packet(data, utf8_decode=False):
        if type(data) == str:
            if data[0] == 'b':
                return Parser.decode_base64_packet(data[1:])

            packet_type = data[0]

            if utf8_decode:
                # TODO catch and throw an customized exception? Or not
                data = data.decode('utf-8')

            packet_type = Parser.packet_type_lists[int(packet_type)]

            if len(data) > 1:
                return {
                    "type": packet_type,
                    "data": data[1:]
                }

            else:
                return {
                    "type": packet_type
                }

        # Binary data
        packet_type = int(chr(data[0]))
        return {
            "type": Parser.packet_type_lists[packet_type],
            "data": data[1:]
        }


    @staticmethod
    def decode_base64_packet(data):
        if data[0] == 'b':
            data = data[1:]
        index = int(data[0])
        packet_type = Parser.packet_type_lists[index]
        data = bytearray(base64.standard_b64decode(data[1:]))
        return {
            "type": packet_type,
            "data": data
        }

    @staticmethod
    def encode_payload(packets, supports_binary=True):
        if supports_binary is True:
            return Parser.encode_payload_as_binary(packets)

        if not packets:
            return '0:'

        if type(packets) not in (tuple, list):
            packets = packets,

        out_buffer = bytearray()
        for packet in packets:
            encoded = Parser.encode_packet(packet, supports_binary)
            out_buffer += '{0}:{1}'.format(str(len(encoded)), encoded)

        return out_buffer

    @staticmethod
    def decode_payload(data):
        if type(data) != str:
            for result in Parser.decode_payload_as_binary(data):
                yield result

        elif not data:
            yield (Parser.error_packet, 0, 1)

        else:
            length_str = ''
            total_length = len(data)

            for i in xrange(0, len(data)):
                ch = data[i]
                if ch != ':':
                    length_str += ch
                else:
                    if length_str == '':
                        yield (Parser.error_packet, 0, 1)

                    length = int(length_str)
                    message = data[i+1: i+1+length]

                    if len(message) != length:
                        yield (Parser.error_packet, 0, 1)

                    if message:
                        packet = Parser.decode_packet(message)
                        yield (packet, i + length, total_length)

                    length_str = ''

            if length_str != '':
                yield (Parser.error_packet, 0, 1)


    @staticmethod
    def encode_payload_as_binary(packets):
        if not packets:
            return empty_byte_array

        if type(packets) not in (tuple, list):
            packets = (packets,)

        out_buffer = bytearray()
        for packet in packets:
            encoded_packet = Parser.encode_packet(packet, supports_binary=True)

            str_len = str(len(encoded_packet))
            str_len = bytearray([int(c) for c in str_len])
            length_buf = bytearray([0]) + str_len + bytearray([255])

            if type(encoded_packet) == str:
                out_buffer += length_buf + bytearray(encoded_packet)
            else:
                out_buffer += length_buf + encoded_packet

        return out_buffer


    @staticmethod
    def decode_payload_as_binary(data):
        buffer_left = data

        packets = []
        while buffer_left:
            str_len = ''
            is_string = buffer_left[0] == 0

            for i in xrange(1, 400):
                if buffer_left[i] == 255:
                    break

                if len(str_len) > 310:
                    yield (Parser.error_packet, 0, 1)

                str_len += str(buffer_left[i])

            buffer_left = buffer_left[len(str_len) + 1:]

            message_len = int(str_len)
            message = buffer_left[1: message_len + 1]
            if is_string:
                message = str(message)

            packets.append(Parser.decode_packet(message))

            buffer_left = buffer_left[message_len + 1:]

        for index, packet in enumerate(packets):
            yield (packet, index, len(packets))
