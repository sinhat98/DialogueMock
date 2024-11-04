from .encoder import EncoderCPC
from .modules import GPT, GPTStereo
from .objective import ObjectiveVAP
from . import util
import os

CPC_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'asset/cpc/60k_epoch4-d0f474de.pt')
VAP_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'asset/vap/vap_state_dict_jp_20hz_2500msec.pt')
