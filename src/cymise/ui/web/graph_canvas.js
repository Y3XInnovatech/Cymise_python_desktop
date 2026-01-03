(() => {
  function setup() {
    const statusEl = document.getElementById("status");
    const fromPyEl = document.getElementById("from-python");
    const pingBtn = document.getElementById("ping-btn");

    window.cymiseReceive = (msg) => {
      fromPyEl.textContent = `Python says: ${msg}`;
    };

    if (!window.qt || !qt.webChannelTransport) {
      statusEl.textContent = "QWebChannel unavailable";
      return;
    }

    new QWebChannel(qt.webChannelTransport, (channel) => {
      const bridge = channel.objects.bridge;
      if (!bridge) {
        statusEl.textContent = "Bridge not found";
        return;
      }

      bridge.pong.connect((msg) => {
        statusEl.textContent = `Pong signal: ${msg}`;
      });

      const sendPing = () => {
        if (typeof bridge.ping === "function") {
          bridge.ping("hello-from-js", (resp) => {
            statusEl.textContent = `Ping sent, return: ${resp}`;
          });
        }
      };

      pingBtn.addEventListener("click", sendPing);
      sendPing();
    });
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    setup();
  } else {
    document.addEventListener("DOMContentLoaded", setup);
  }
})();
