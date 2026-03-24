from qtconsole.client import QtKernelClient
c = QtKernelClient()
print(hasattr(c, 'get_iopub_msg'))
print(hasattr(c, 'iopub_channel'))
