from qtconsole.client import QtKernelClient
c = QtKernelClient()
print(hasattr(c.iopub_channel, 'get_msg'))
