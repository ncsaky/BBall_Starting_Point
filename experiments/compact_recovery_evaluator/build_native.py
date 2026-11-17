"""Use only existing independent CLT installation; no host changes/install."""
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
from .verification import OUT,BASE,ROOT

LIB=BASE/'native-build/compact_geometry.dylib'
SOURCE=ROOT/'experiments/compact_recovery_evaluator/native/geometry.c'

def build():
    folder=LIB.parent;folder.mkdir(exist_ok=True)
    compiler=Path('/Library/Developer/CommandLineTools/usr/bin/clang');sdk=Path('/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk')
    report={'compiler':str(compiler),'sdk':str(sdk),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'machine':platform.machine(),'system':platform.system(),'host_changes':False}
    if not compiler.exists() or not sdk.exists():report.update(available=False,reason='Existing independent toolchain unavailable; Python fallback retained')
    else:
        flags=['-O3','-std=c11','-dynamiclib','-fPIC','-fno-fast-math','-fno-associative-math','-ffp-contract=off','-frounding-math','-fexcess-precision=standard','-Wall','-Wextra','-Werror','-isysroot',str(sdk),'-B/Library/Developer/CommandLineTools/usr/bin']
        command=[str(compiler),*flags,str(SOURCE),'-o',str(LIB)];t=time.perf_counter();r=subprocess.run(command,capture_output=True,text=True,timeout=30);report.update(command=command,build_s=time.perf_counter()-t,returncode=r.returncode);(folder/'build.log').write_text(r.stdout+r.stderr)
        if r.returncode:report.update(available=False,reason='Build failed; no retries/host changes, Python fallback retained')
        else:
            t=time.perf_counter();lib=ctypes.PyDLL(str(LIB));report.update(available=lib.compact_geometry_abi()==1,first_observed_load_s=time.perf_counter()-t,binary_sha256=hashlib.sha256(LIB.read_bytes()).hexdigest(),binary_bytes=LIB.stat().st_size,compiler_version=subprocess.check_output([str(compiler),'--version'],text=True))
    (OUT/'native-build.json').write_text(json.dumps(report,indent=2)+'\n');return report


def sanitize():
    folder=LIB.parent;compiler='/Library/Developer/CommandLineTools/usr/bin/clang';harness=SOURCE.with_name('check.c');target=folder/'geometry-ubsan'
    command=[compiler,'-O1','-g','-std=c11','-fsanitize=undefined','-fno-sanitize-recover=all','-fno-fast-math','-fno-associative-math','-ffp-contract=off','-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-B/Library/Developer/CommandLineTools/usr/bin',str(harness),'-o',str(target)]
    result={'command':command,'scope':'512 bounded standalone numeric rows,buffer canaries,invalid ABI guards; ASan not claimed or retried (prior toolchain initialization stall),cross-platform/frozen packaging untested'}
    try:
        built=subprocess.run(command,capture_output=True,text=True,timeout=30);result.update(build_returncode=built.returncode,build_output=built.stdout+built.stderr)
        if built.returncode==0:
            t=time.perf_counter();run=subprocess.run([str(target)],capture_output=True,text=True,timeout=10);result.update(run_returncode=run.returncode,run_s=time.perf_counter()-t,output=run.stdout+run.stderr,passed=run.returncode==0)
        else:result['passed']=False
    except (OSError,subprocess.TimeoutExpired) as exc:result.update(passed=False,reason=str(exc))
    (OUT/'native-ubsan.json').write_text(json.dumps(result,indent=2)+'\n');return result
