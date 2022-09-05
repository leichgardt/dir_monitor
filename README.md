# Dir monitor

This is a directory content monitor - client-server application.
The server watches for changes in the directory and quickly updates it on the client if some content changes. 
The client app is a simple web page with a table of files. 
The client and the server can work independently.

Web application and monitor are split into two programs.

Monitor parameters specifies at script launch as command arguments.
Other settings specifies in environment variables.

# Features
* Asyncio
* Backend microservice architecture: split monitor and web-server
* Recursive monitoring of directories

Microservices allow to horizontal scaling of server.
One monitor and pool of servers can service many clients.

The client `index.html` file is delivering by the server, 
but for more client-server independency it can be achieved 
by Nginx static files distributing (or another webserver).

***

# Requirements
* Python 3.8+
* Redis

# Installation
Create virtual environment and install requirements
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# Preparing
Before installation, you need to add a Redis URL to environment variables
```
export REDIS_FW_URL=redis://localhost/0
export REDIS_FW_CHANNEL=file_watcher
```

# Run
At first run `monitor.py` to start a directory monitoring.
```
python monitor.py [path]
```

Next you need to launch a server
```
uvicorn app:app
```

After that you can go to http://127.0.0.1:8000/
