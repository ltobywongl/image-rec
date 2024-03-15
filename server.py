import base64
import json
import socket
import threading
from queue import Queue
from PIL import Image
import numpy as np
from tensorflow.keras.applications.inception_v3 import InceptionV3, preprocess_input, decode_predictions
model = InceptionV3(weights='imagenet')

# Create a queue to pass client sockets between threads
client_queue = Queue()

def decodeImage(encoded_image: str):
    image_data = base64.b64decode(encoded_image)
    with open('image.png', 'wb') as outfile:     
        outfile.write(image_data)
        return outfile

def handle_client(client_socket):
    while True:
        print("Handling client")
        # Read the message from the client
        data = client_socket.recv(1024).decode('utf-8')
        while not data.endswith("##END##"):
            data += client_socket.recv(1024).decode('utf-8')
        if not data:
            break

        # Parse the JSON data
        message = json.loads(data)
        encoded_image = message['image']
        chat_id = message['chat_id']

        image = decodeImage(encoded_image)
        image_array = preprocess_input(image)

        predictions = model.predict(image_array)
        decoded_predictions = decode_predictions(predictions, top=5)[0]

        # Compose the response dictionary
        response = {
            'predictions': [
                {'label': label, 'proba': float(proba)}
                for label, _, proba in decoded_predictions
            ],
            'chat_id': chat_id
        }

        # Send the response back to the client
        response_json = json.dumps(response)
        client_socket.send(response_json.encode('utf-8'))
        break

    client_socket.close()

def client_thread():
    while True:
        client_socket = client_queue.get()
        handle_client(client_socket)

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 8000))
    server_socket.listen(1)

    threading.Thread(target=client_thread, daemon=True).start()

    print('Server is running and listening for connections...')

    while True:
        client_socket, address = server_socket.accept()
        print(f'Connected to client: {address}')
        client_queue.put(client_socket)

if __name__ == '__main__':
    main()