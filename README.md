# Piperum

Handy subprocess runner with pipelines support.

* no external dependencies
* supports timeouts
* do not use sh/bash etc as a backend
* deals with control terminal and process groups: subprocesses are able to securely read user input (like sudo does)

## Usage

```python 
from piperum import piperum as pr
```


__Subprocess run variants__
```python 
# Run single process in foreground
## equivalent to sh: '/usr/bin/ls -1'
pr.run("/usr/bin/ls -1")  # raises subprocess.CalledProcessError if returncode != 0

## run with timeout for waiting process completion
## valid for [run, cap]
pr.run("sleep 10", timeout=5)  # raises subprocess.TimeoutExpired

# Run pipelined processes in foreground
## equivalent to sh: '/usr/bin/ls -1 | /usr/bin/grep tmp'
pr.run("/usr/bin/ls -1", "/usr/bin/grep tmp")

# Run pipelined processes in foreground and capture its output
## equivalent to sh: '$(/usr/bin/ls -1 | /usr/bin/grep tmp)'
some_var = pr.cap("/usr/bin/ls -1", "/usr/bin/grep tmp")

# Run pipelined processes in backgtound
## equivalent to sh: '/usr/bin/curl http://example.com/somearch.tgz -O - | /usr/bin/tar -xzf - &'
bgtask = pr.run_bg("/usr/bin/curl http://example.com/somearch.tgz -O -", "/usr/bin/tar -xzf -")
bgtask.pid                 # background process (or process group if pipeline) pid
bgtask.is_alive            # True if process is still running, otherwise - False
bgtask.returncode          # returncode if process is finished, otherwise - None
bgtasl.wait(timeout=None)  # blocking wait until process finish, optional timeout
bgtask.kill(signal=os.SIGKILL)  # send signal to procees
```

__Standard streams redirection__
```python
# Read stdin

## valid for [run, cap, run_bg]
## equivalent to sh: 'cat /some_path/somefile.sql | /usr/bin/psql -d domedb'
pr.run("/usr/bin/psql -d somedb", inpfl="/some_path/somefile.sql")

## valid for [run, cap]
## equivalent to sh: 'echo "SELECT * FROM table;" | /usr/bin/psql -d domedb'
pr.run("/usr/bin/psql -d somedb", inptxt="SELECT * FROM table;")


# Redirect stdout
 
## valid for [run, run_bg]
## equivalent to sh: '/usr/bin/ls -1 > /some_path/filename.txt'
pr.run("/usr/bin/ls -1", outfl="/some_path/filename.txt")

## valid for [run, run_bg]
## equivalent to sh: '/usr/bin/ls -1 >> /some_path/filename.txt'
pr.run("/usr/bin/ls -1", outfl="+/some_path/filename.txt")


# Redirect stderr

## [valid](valid) for [run, cap, run_bg]
## equivalent to sh: '/usr/bin/ls -1 2>/some_path/filename.txt'
pr.run("/usr/bin/ls -1", errfl="/some_path/filename.txt")

## equivalent to sh: '/usr/bin/ls -1 2>>/some_path/filename.txt'
pr.run("/usr/bin/ls -1", errfl="+/some_path/filename.txt")

## valid for [run, cap, run_bg]
## equivalent to sh: '/usr/bin/ls -1 2>&1'
pr.run("/usr/bin/ls -1", err2out=True)
```

__Change process environment__
```python
# Working directory
## equivalent to sh: 'pushd /somepath; /usr/bin/pwd; popd'
pr(cwd="/somepath").run("/usr/bin/pwd")

# Extra environment variables
## equivalent to sh: 'PGPASSWD="secret" /usr/bin/psql -d somedb'
pr(PGPASSWD="secret").run("/usr/bin/psql -d somedb")

# You're able to assign it to variable for reuse
pr2 = pr(cwd="../somepath", PGPASSWD="secret")
pr2.run("/usr/bin/psql -d somedb")
pr2.run("/usr/bin/pwd")

# or
with pr(cwd="../somepath", PGPASSWD="secret") as pt2:
    pr2.run("/usr/bin/psql -d somedb")
    pr2.run("/usr/bin/pwd")
```
