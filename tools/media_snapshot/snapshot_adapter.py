"""Trusted Git snapshot input; artifact/PASS/payload hashes do not establish authority."""
from pathlib import Path
import sys
PACKAGE=Path(__file__).resolve().parent/'git_snapshot'
sys.path.insert(0,str(PACKAGE))
from site_input import materialize,resolve_request,strict,configured
