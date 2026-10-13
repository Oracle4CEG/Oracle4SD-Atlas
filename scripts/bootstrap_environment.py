"""Create a pinned scientific Python without relying on host venv/ensurepip."""
import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UV_VERSION = "0.9.5"
PYTHON_VERSION = "3.12.12"


def bootstrap(output, requirements=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    log = output / "bootstrap.log"
    env = os.environ.copy()
    env.update(UV_PYTHON_INSTALL_DIR=str(output/"python"), UV_CACHE_DIR=str(output/"cache"),
               MPLBACKEND="Agg", PYTHONNOUSERSITE="1")
    commands=[]
    def run(args):
        args=[str(x) for x in args]
        result=subprocess.run(args,env=env,capture_output=True,text=True)
        commands.append(dict(command=args,exit_code=result.returncode))
        with log.open("a") as f:
            f.write(json.dumps(args)+"\n"+result.stdout+result.stderr+"\n")
        if result.returncode:
            raise RuntimeError(f"Environment setup failed; full command and traceback in {log}\n"+result.stdout+result.stderr)
        return result.stdout
    try:
        target=output/"bootstrap-tools"
        run([sys.executable,"-m","pip","install","--disable-pip-version-check","--no-deps","--target",target,f"uv=={UV_VERSION}"])
        uv=target/("Scripts/uv.exe" if os.name=="nt" else "bin/uv")
        if not uv.is_file():
            candidates=list(target.rglob("uv.exe" if os.name=="nt" else "uv"))
            uv=next((p for p in candidates if p.is_file()),uv)
        run([uv,"venv","--python",PYTHON_VERSION,"--python-preference","only-managed","--seed",output/"scientific"])
        python=output/"scientific"/("Scripts/python.exe" if os.name=="nt" else "bin/python")
        run([uv,"pip","install","--python",python,"-r",requirements or ROOT/"requirements-release.txt"])
        run([python,"-m","pip","check"])
        freeze=run([python,"-m","pip","freeze"])
        (output/"scientific.freeze.txt").write_text(freeze)
        scientific=json.loads(run([python,"-c","import sys,platform,json; print(json.dumps({'python':platform.python_version(),'executable':sys.executable}))"]))
        identity=dict(host_python=platform.python_version(),host_executable=sys.executable,
                      scientific=scientific,uv_version=UV_VERSION,commands=commands,passed=True)
        (output/"environment.json").write_text(json.dumps(identity,indent=2)+"\n")
        return python
    except Exception:
        (output/"environment.json").write_text(json.dumps(dict(host_python=platform.python_version(),commands=commands,passed=False),indent=2)+"\n")
        raise


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True)
    p.add_argument("--requirements")
    a=p.parse_args()
    print(bootstrap(a.output,a.requirements))
