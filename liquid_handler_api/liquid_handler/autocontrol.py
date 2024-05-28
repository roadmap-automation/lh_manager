"""Interface for autocontrol"""

import requests
import threading
from autocontrol.task_struct import Task

port = 5004

def submit_task(task: Task):
    #print('Submitting Task: ' + task.tasks[0].device + ' ' + task.task_type + 'Sample: ' + str(task.sample_id) + '\n')
    print('Submitting Task: ' + task.tasks[0].device + ' ' + task.task_type + '\n')
    url = 'http://localhost:' + str(port) + '/put'
    headers = {'Content-Type': 'application/json'}
    data = task.model_dump_json()
    response = requests.post(url, headers=headers, data=data)
    print('Autocontrol response: ', response)

def async_submit(task: Task):

    threading.Thread(target=submit_task, args=(task)).start()
