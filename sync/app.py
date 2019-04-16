import time
import logging
import logging.config
import sys
import configparser 
import paramiko


logger = logging.getLogger(__name__)
# logging.config.fileConfig('./confs/logging.conf')
config = configparser.ConfigParser()
config.read('./configs/sync.conf')


def sync():
    while True:
        # ssh = paramiko.SSHClient() 
        # ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        # ssh.connect(server, username=username, password=password)
        # sftp = ssh.open_sftp()
        # sftp.put(config.get('MAIN', 'LOCAL_PATH'), config.get('MAIN', 'REMOTE_PATH'))
        # sftp.close()
        # ssh.close()

        print('SYNC DONE')

        time.sleep(config.getint('MAIN', 'SLEEP_TIME'))


if __name__ == '__main__':
    print('true')
    sync()