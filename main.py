import time
import subprocess
import select

f = subprocess.Popen(['tail', '-F', '/Users/v-brandon.sturgeon/Code/personal/cfc_rcon_reader/test/output.log'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
p = select.poll()
p.register(f.stdout)

while True:
    if p.poll(1):
        print(f.stdout.readline())
    time.sleep(0.01)
