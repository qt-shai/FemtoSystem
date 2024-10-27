# PyCharm Debug Crash Troubleshooting Guide

If your debug session in PyCharm crashes, try the following steps to resolve the issue:

1. **Open PyCharm.**
2. Press `Shift + Shift` to open the **Search Everywhere** feature.
3. In the popup, type `Registry` and press **Enter**.
4. From the list of results, find **Registry** and click on it.
5. In the new popup, locate the setting: `python.debug.asyncio.repl`.
6. Uncheck the checkbox next to `python.debug.asyncio.repl`.
7. Press **Close** to exit the Registry settings.
8. Restart the PyCharm IDE.

Disabling the `asyncio` support in the debugger can help prevent crashes during debugging sessions.

---

### Notes
Disabling `asyncio` support may limit certain asynchronous debugging features, so re-enable it only if necessary.
