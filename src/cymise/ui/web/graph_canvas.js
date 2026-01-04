(() => {
  function setup() {
    const statusEl = document.getElementById("status");
    const fromPyEl = document.getElementById("from-python");
    const pingBtn = document.getElementById("ping-btn");
    const cyContainer = document.createElement("div");
    cyContainer.id = "cy";
    cyContainer.style.height = "600px";
    cyContainer.style.border = "1px solid #ccc";
    document.body.appendChild(cyContainer);

    let cy = null;

    window.cymiseReceive = (msg) => {
      fromPyEl.textContent = `Python says: ${msg}`;
    };

    const buildCy = () => {
      cy =
        cy ||
        cytoscape({
          container: cyContainer,
          elements: [],
          style: [
            {
              selector: "node",
              style: {
                "background-color": "#5DADE2",
                label: "data(label)",
                "font-size": 12,
                color: "#fff",
                "text-valign": "center",
              },
            },
            {
              selector: "edge",
              style: {
                "line-color": "#888",
                "target-arrow-color": "#888",
                "target-arrow-shape": "triangle",
                "curve-style": "bezier",
                width: 2,
                label: "data(label)",
                "font-size": 10,
                "text-background-color": "#fff",
                "text-background-opacity": 0.6,
              },
            },
            { selector: ".ok", style: { "background-color": "#28a745", "line-color": "#28a745" } },
            {
              selector: ".warning",
              style: { "background-color": "#ffc107", "line-color": "#ffc107" },
            },
            { selector: ".error", style: { "background-color": "#dc3545", "line-color": "#dc3545" } },
          ],
          layout: { name: "breadthfirst", fit: true, padding: 30 },
          wheelSensitivity: 0.2,
        });

      cy.on("tap", "node", (evt) => {
        const node = evt.target;
        window.bridge && window.bridge.select_element(node.id(), "node");
      });
      cy.on("tap", "edge", (evt) => {
        const edge = evt.target;
        window.bridge && window.bridge.select_element(edge.id(), "edge");
      });
    };

    const rebuildGraph = (payload) => {
      buildCy();
      cy.batch(() => {
        cy.elements().remove();
        const elements = [];
        (payload.nodes || []).forEach((n) => {
          elements.push({
            data: { id: n.id, label: n.label || n.id },
            classes: validationClass(n.validation),
          });
        });
        (payload.edges || []).forEach((e) => {
          elements.push({
            data: {
              id: e.id,
              source: e.source,
              target: e.target,
              label: e.label || "",
            },
            classes: validationClass(e.validation),
          });
        });
        cy.add(elements);
        cy.layout({ name: "breadthfirst", fit: true, padding: 30 }).run();
        cy.fit();
      });
    };

    window.cyUpdateNodes = (nodes) => {
      if (!cy) return;
      cy.batch(() => {
        (nodes || []).forEach((n) => {
          const existing = cy.getElementById(n.id);
          if (existing && existing.length) {
            existing.data("label", n.label || n.id);
            existing.classes(validationClass(n.validation));
          } else {
            cy.add({
              data: { id: n.id, label: n.label || n.id },
              classes: validationClass(n.validation),
            });
          }
        });
      });
    };

    window.cyUpdateEdges = (edges) => {
      if (!cy) return;
      cy.batch(() => {
        (edges || []).forEach((e) => {
          const existing = cy.getElementById(e.id);
          if (existing && existing.length) {
            existing.data({ label: e.label || "", source: e.source, target: e.target });
            existing.classes(validationClass(e.validation));
          } else {
            cy.add({
              data: { id: e.id, source: e.source, target: e.target, label: e.label || "" },
              classes: validationClass(e.validation),
            });
          }
        });
      });
    };

    window.cyRemoveNodes = (nodeIds) => {
      if (!cy) return;
      const ids = Array.isArray(nodeIds) ? nodeIds : [];
      cy.batch(() => {
        ids.forEach((id) => {
          const ele = cy.getElementById(id);
          if (ele && ele.length) {
            cy.remove(ele);
          }
        });
      });
    };

    window.cyRemoveEdges = (edgeIds) => {
      if (!cy) return;
      const ids = Array.isArray(edgeIds) ? edgeIds : [];
      cy.batch(() => {
        ids.forEach((id) => {
          const ele = cy.getElementById(id);
          if (ele && ele.length) {
            cy.remove(ele);
          }
        });
      });
    };


    window.cyApplyValidation = (map) => {
      if (!cy || !map) return;
      Object.entries(map).forEach(([id, state]) => {
        const ele = cy.getElementById(id);
        if (ele && ele.length) {
          ele.classes(validationClass({ severity: state }));
        }
      });
    };

const validationClass = (validation) => {
  if (!validation) return "ok";

  // Preferred schema (matches importer GraphService payload):
  // { issues: [{ severity: "error"|"warning", ... }], is_ok: boolean }
  const issues = validation.issues;
  if (Array.isArray(issues)) {
    const hasError = issues.some((i) => i && i.severity === "error");
    if (hasError) return "error";
    const hasWarning = issues.some((i) => i && i.severity === "warning");
    if (hasWarning) return "warning";
  }

  if (typeof validation.is_ok === "boolean") {
    return validation.is_ok ? "ok" : "warning";
  }

  // Backward/alternate schema support (manual styling calls)
  const sev = validation.severity || validation.status;
  if (sev === "error") return "error";
  if (sev === "warning") return "warning";
  return "ok";
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
      window.bridge = bridge;

      bridge.pong.connect((msg) => {
        statusEl.textContent = `Pong signal: ${msg}`;
      });

      bridge.graph_data.connect((payload) => {
        statusEl.textContent = "Graph received";
        rebuildGraph(payload || {});
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

      if (typeof bridge.request_graph === "function") {
        bridge.request_graph();
      }
    });
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    setup();
  } else {
    document.addEventListener("DOMContentLoaded", setup);
  }
})();
