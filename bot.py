import json
from queue import Queue
import socket
import threading
from PIL import Image
import requests
import time
import telepot
from telepot.loop import MessageLoop
from io import BytesIO
import base64

receiveQueue = Queue()
sendQueue = Queue()
bot = telepot.Bot("6723647884:AAGv_6Uva6pg2FnB3IGg2hHt36pvmP6tKhA")

def format_response(server_response):
    formatted_response = ""
    for i, item in enumerate(server_response, start=1):
        name = item['name']
        proba = item['proba']
        formatted_response += f"{i}. {name} ({proba:.4f})\n"
    return formatted_response.strip()

def send_data_to_server(imageBytes: bytes, chat_id):
    data = {
        'image': imageBytes.decode('utf-8'),
        'chat_id': chat_id
    }
    data_json = json.dumps(data) + "##END##"
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client_socket.connect(('localhost', 8000))
        client_socket.send(data_json.encode('utf-8'))

        response_json = client_socket.recv(1024).decode('utf-8')
        while not response_json.endswith("##END##"):
            response_json += client_socket.recv(1024).decode('utf-8')
        response = json.loads(response_json[:-7])

        print('Received response from server:', response)
        return format_response(response["predictions"])
    finally:
        client_socket.close()

def handleReceive(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    if content_type == 'text':
        url = msg['text']
        try:
            response = requests.get(url)
        except:
            return bot.sendMessage(chat_id, f"Failed to download image.")
        if str(response.status_code)[0] == '2':
            image_data = response.content
            image = Image.open(BytesIO(image_data))
            print("Putting data to queue")
            receiveQueue.put([chat_id, image])
        else:
            bot.sendMessage(chat_id, f"Failed to download image. Status code: {response.status_code}")
    elif content_type == 'photo':
        bot.download_file(msg['photo'][-1]['file_id'], 'file.png') 
        image = Image.open('file.png')
        receiveQueue.put([chat_id, image])

def process_receive_queue():
    while True:
        if not receiveQueue.empty():
            try:
                # Read data from receive queue
                chat_id, image = receiveQueue.get()
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                encoded_image = base64.b64encode(buffered.getvalue())
                print(f"Handling message in chat {chat_id}, image: {image}, strlen: {len(encoded_image)}")

                # Talk with server
                server_response = send_data_to_server(encoded_image, chat_id)

                # Thread3 send response
                sendQueue.put([chat_id, server_response])
            except Exception as e:
                print("Failed to handle receive queue: ", e)
            finally:
                receiveQueue.task_done()
        time.sleep(1)

def process_send_queue():
    while True:
        if not sendQueue.empty():
            try:
                chat_id, server_response = sendQueue.get()
                print(f"Processing send queue, chat_id: {chat_id}, server_response: {server_response}")
                bot.sendMessage(chat_id, server_response)
            except Exception as e:
                print("Failed to handle send queue: ", e)
            finally:
                sendQueue.task_done()
        time.sleep(1)

if __name__ == "__main__":
    MessageLoop(bot, handleReceive).run_as_thread()
    threading.Thread(target=process_receive_queue, daemon=True).start()
    threading.Thread(target=process_send_queue, daemon=True).start()
    while True:
        time.sleep(10)
