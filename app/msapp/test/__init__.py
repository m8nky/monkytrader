import logging

_l = logging.getLogger()
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_ch.setFormatter(_formatter)
_l.addHandler(_ch)
