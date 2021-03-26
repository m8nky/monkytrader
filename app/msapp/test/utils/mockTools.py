from unittest import mock
import importlib

# Dirty-dirty - this little bi** ensures I don't have to change the original project, while I can mock modules imports without harming the nested classes with the same name.
# Found at: https://stackoverflow.com/questions/52324568/how-to-mock-a-function-called-in-a-function-inside-a-module-with-the-same-name/
# Avoids: AttributeError: <class 'vmacro.gateway.ContentHub.ContentHub'> does not have the attribute 'requests'
#         when doing - __init__.py: from .ContentHub import ContentHub
#                      ContentHub.py: import requests
#                      TestContentHub.py: @module.patch('vmacro.gateway.ContentHub.requests')
def mock_module_patch(*args, **kwargs):
    target = args[0]
    components = target.split('.')
    for i in range(len(components), 0, -1):
        try:
            # attempt to import the module
            imported = importlib.import_module('.'.join(components[:i]))
            # module was imported, let's use it in the patch
            patch = mock.patch(*args, **kwargs)
            patch.getter = lambda: imported
            patch.attribute = '.'.join(components[i:])
            return patch
        except Exception:
            pass
    # did not find a module, just return the default mock
    return mock.patch(*args, **kwargs)
