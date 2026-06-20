(function () {
  const RENDER_EVENT = "streamlit:render";
  const events = new EventTarget();

  function send(type, data) {
    window.parent.postMessage(
      {
        isStreamlitMessage: true,
        type,
        ...data,
      },
      "*",
    );
  }

  window.Streamlit = {
    RENDER_EVENT,
    events,
    setComponentReady() {
      send("streamlit:componentReady", { apiVersion: 1 });
    },
    setFrameHeight(height) {
      send("streamlit:setFrameHeight", { height });
    },
    setComponentValue(value) {
      send("streamlit:setComponentValue", { value, dataType: "json" });
    },
  };

  window.addEventListener("message", (event) => {
    if (!event.data || event.data.type !== RENDER_EVENT) return;
    events.dispatchEvent(new CustomEvent(RENDER_EVENT, { detail: event.data }));
  });
})();
