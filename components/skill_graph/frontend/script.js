let graphData = { skills: [], levels: {}, remaining_points: 0, settings: {} };
let selectedSkillId = null;
let lastRenderKey = null;
let layoutMetrics = { width: 0, height: 0 };
let resizeFrame = null;
let lastAvailableWidth = 0;
sessionStorage.removeItem("skillGraphSelectedSkill");

const viewport = document.getElementById("viewport");
const canvas = document.getElementById("canvas");
const edgesSvg = document.getElementById("edges");
const nodesEl = document.getElementById("nodes");

function emit(action, skillId) {
  rememberViewportState();
  selectedSkillId = skillId;
  applyOptimisticLevel(action, skillId);
  updateDynamicState();
  const event = {
    action,
    skill_id: skillId,
    event_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
  };
  window.Streamlit.setComponentValue(event);
}

function renderKey(data) {
  const settings = data.settings || {};
  return JSON.stringify({
    skills: (data.skills || []).map((skill) => [skill.id, skill.x, skill.y, skill.category, skill.prerequisites, skill.required_points, skill.max_level]),
    collapsed: settings.collapsed_trees || {},
    treeOrder: settings.tree_order || [],
    tooltips: !!settings.show_skill_tooltips,
  });
}

function skillByIdFromData() {
  return new Map((graphData.skills || []).map((skill) => [skill.id, skill]));
}

function updateDynamicState() {
  const byId = skillByIdFromData();
  document.querySelectorAll(".skill-node").forEach((node) => {
    const skill = byId.get(node.dataset.skillId);
    if (!skill) return;
    const level = graphData.levels[skill.id] || 0;
    node.classList.toggle("available", !!skill.unlocked);
    node.classList.toggle("locked", !skill.unlocked);
    node.classList.toggle("invested", level > 0);
    node.classList.toggle("maxed", level >= skill.max_level);
    const levelEl = node.querySelector(".skill-level");
    if (levelEl) levelEl.textContent = `${level}/${skill.max_level}`;
    const tooltipEl = node.querySelector(".tooltip");
    if (tooltipEl) tooltipEl.innerHTML = tooltip(skill);
  });
  document.querySelectorAll(".edge").forEach((edge) => {
    const parent = byId.get(edge.dataset.source);
    const child = byId.get(edge.dataset.target);
    if (!parent || !child) return;
    edge.classList.remove("active", "available", "locked");
    edge.classList.add(edgeStatus(parent, child));
  });
  updateTreeSpentLabels();
}

function applyOptimisticLevel(action, skillId) {
  const levels = { ...(graphData.levels || {}) };
  const skillsById = skillByIdFromData();

  function isUnlocked(id) {
    const skill = skillsById.get(id);
    if (!skill) return false;
    return skill.prerequisites.every((parentId) => (levels[parentId] || 0) >= skill.required_points);
  }

  function fillPrerequisites(id) {
    const skill = skillsById.get(id);
    if (!skill) return;
    skill.prerequisites.forEach((parentId) => {
      fillPrerequisites(parentId);
      const parent = skillsById.get(parentId);
      if (!parent) return;
      levels[parentId] = Math.min(parent.max_level, Math.max(levels[parentId] || 0, skill.required_points));
    });
  }

  function hasInvalidPrerequisites(id) {
    const skill = skillsById.get(id);
    if (!skill || (levels[id] || 0) <= 0) return false;
    return skill.prerequisites.some((parentId) => (levels[parentId] || 0) < skill.required_points);
  }

  function clearInvalidDownstream() {
    let changed = true;
    while (changed) {
      changed = false;
      skillsById.forEach((skill, id) => {
        if (!hasInvalidPrerequisites(id)) return;
        levels[id] = 0;
        changed = true;
      });
    }
  }

  if (action === "increment") {
    const skill = skillsById.get(skillId);
    if (!skill || (levels[skillId] || 0) >= skill.max_level) return;
    if (!isUnlocked(skillId)) {
      if (!graphData.settings?.auto_allocate) return;
      fillPrerequisites(skillId);
      if (!isUnlocked(skillId)) return;
    }
    levels[skillId] = (levels[skillId] || 0) + 1;
  }
  if (action === "decrement") {
    if ((levels[skillId] || 0) <= 0) return;
    levels[skillId] = Math.max(0, (levels[skillId] || 0) - 1);
    clearInvalidDownstream();
  }
  graphData = { ...graphData, levels };
}

function rememberViewportState() {
  sessionStorage.setItem(
    "skillGraphViewport",
    JSON.stringify({ left: window.scrollX, top: window.scrollY }),
  );
}

function restoreViewportState() {
  const raw = sessionStorage.getItem("skillGraphViewport");
  if (!raw) return;
  try {
    const state = JSON.parse(raw);
    if (typeof state.left === "number" && typeof state.top === "number") window.scrollTo(state.left, state.top);
  } catch {
    sessionStorage.removeItem("skillGraphViewport");
  }
}

function emitTreeEvent(action, payload) {
  window.Streamlit.setComponentValue({
    action,
    event_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    ...payload,
  });
}

function toggleTree(treeName) {
  const settings = graphData.settings || {};
  const collapsedTrees = { ...(settings.collapsed_trees || {}) };
  const isCollapsed = collapsedTrees[treeName] !== false;
  collapsedTrees[treeName] = !isCollapsed;
  graphData = {
    ...graphData,
    settings: { ...settings, collapsed_trees: collapsedTrees },
  };
  render();
  emitTreeEvent("toggle_tree", { tree: treeName, collapsed: collapsedTrees[treeName] });
}

function openSkillDocs(skill) {
  let baseUrl = document.referrer || "/";
  try {
    if (window.parent && window.parent.location) baseUrl = window.parent.location.href;
  } catch {
    // Fall back to document.referrer when the iframe cannot access the parent URL.
  }
  const url = new URL(baseUrl, window.location.origin);
  url.searchParams.set("doc_tree", skill.category || "Skills");
  url.searchParams.set("skill", skill.id);
  url.hash = "target-skill";
  window.open(url.toString(), "_blank", "noopener");
}

function treeGroups() {
  const groups = new Map();
  (graphData.skills || []).forEach((skill) => {
    const tree = skill.category || "Skills";
    if (!groups.has(tree)) groups.set(tree, []);
    groups.get(tree).push(skill);
  });
  const configured = (graphData.settings && graphData.settings.tree_order) || [];
  const names = [...configured.filter((name) => groups.has(name)), ...[...groups.keys()].filter((name) => !configured.includes(name))];
  return names.map((name) => [name, groups.get(name)]);
}

function treeSpentPoints(skills) {
  return skills.reduce((total, skill) => {
    const level = graphData.levels[skill.id] || 0;
    return total + level * (skill.point_cost_per_level || 1);
  }, 0);
}

function updateTreeSpentLabels() {
  const spentByTree = new Map(treeGroups().map(([treeName, skills]) => [treeName, treeSpentPoints(skills)]));
  document.querySelectorAll(".tree-header").forEach((header) => {
    const treeName = header.dataset.tree;
    if (!spentByTree.has(treeName)) return;
    const label = header.querySelector(".tree-title");
    if (label) label.textContent = `${treeName} Skills (${spentByTree.get(treeName)})`;
  });
}

function skillById() {
  return new Map((graphData.skills || []).map((skill) => [skill.id, skill]));
}

function ancestorEdges(skillId) {
  const byId = skillById();
  const edges = [];
  const seen = new Set();

  function visit(childId) {
    const child = byId.get(childId);
    if (!child) return;
    child.prerequisites.forEach((parentId) => {
      const key = `${parentId}->${childId}`;
      if (seen.has(key)) return;
      seen.add(key);
      edges.push([parentId, childId]);
      visit(parentId);
    });
  }

  visit(skillId);
  return edges;
}

function layoutSkills() {
  const collapsed = (graphData.settings && graphData.settings.collapsed_trees) || {};
  const positioned = new Map();
  let offsetY = 24;
  let maxX = 900;
  treeGroups().forEach(([treeName, skills]) => {
    const expanded = collapsed[treeName] === false;
    const localMaxY = Math.max(...skills.map((skill) => skill.y), 0);
    const localMaxX = Math.max(...skills.map((skill) => skill.x), 0);
    maxX = Math.max(maxX, localMaxX + 170);
    skills.forEach((skill) => {
      positioned.set(skill.id, { ...skill, displayX: skill.x + 18, displayY: skill.y + offsetY + 64, treeName, hidden: !expanded });
    });
    offsetY += expanded ? localMaxY + 170 : 68;
  });
  return { positioned, height: Math.max(offsetY + 80, 720), width: maxX };
}

function edgeStatus(parent, child) {
  const parentLevel = graphData.levels[parent.id] || 0;
  if (parentLevel >= child.required_points) return "active";
  if (child.unlocked) return "available";
  return "locked";
}

function nodeRect(node, padding = 10) {
  return {
    left: node.displayX - 63 - padding,
    right: node.displayX + 63 + padding,
    top: node.displayY - 54 - padding,
    bottom: node.displayY + 54 + padding,
  };
}

function pointInRect(point, rect) {
  return point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom;
}

function ccw(a, b, c) {
  return (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x);
}

function segmentsIntersect(a, b, c, d) {
  return ccw(a, c, d) !== ccw(b, c, d) && ccw(a, b, c) !== ccw(a, b, d);
}

function segmentIntersectsRect(start, end, rect) {
  if (pointInRect(start, rect) || pointInRect(end, rect)) return true;
  const topLeft = { x: rect.left, y: rect.top };
  const topRight = { x: rect.right, y: rect.top };
  const bottomRight = { x: rect.right, y: rect.bottom };
  const bottomLeft = { x: rect.left, y: rect.bottom };
  return (
    segmentsIntersect(start, end, topLeft, topRight) ||
    segmentsIntersect(start, end, topRight, bottomRight) ||
    segmentsIntersect(start, end, bottomRight, bottomLeft) ||
    segmentsIntersect(start, end, bottomLeft, topLeft)
  );
}

function edgeWouldCrossNode(start, end, parent, child, nodes) {
  return nodes.some((node) => {
    if (node.hidden || node.id === parent.id || node.id === child.id) return false;
    return segmentIntersectsRect(start, end, nodeRect(node));
  });
}

function pathCrossCount(points, parent, child, nodes) {
  let count = 0;
  for (let index = 0; index < points.length - 1; index += 1) {
    if (edgeWouldCrossNode(points[index], points[index + 1], parent, child, nodes)) count += 1;
  }
  return count;
}

function sideRoutePath(parent, child, nodes) {
  const nodeOffset = 31;
  const verticalDirection = child.displayY >= parent.displayY ? 1 : -1;
  const start = { x: parent.displayX, y: parent.displayY + nodeOffset * verticalDirection };
  const end = { x: child.displayX, y: child.displayY - nodeOffset * verticalDirection };
  const candidateXs = [parent.displayX + 104, parent.displayX - 104];
  const sideX = candidateXs.reduce((best, candidate) => {
    const bestCount = pathCrossCount([start, { x: best, y: start.y }, { x: best, y: end.y }, end], parent, child, nodes);
    const candidateCount = pathCrossCount([start, { x: candidate, y: start.y }, { x: candidate, y: end.y }, end], parent, child, nodes);
    return candidateCount < bestCount ? candidate : best;
  }, candidateXs[0]);
  const corner = 16;
  const horizontalDirection = sideX >= parent.displayX ? 1 : -1;
  return [
    `M ${start.x} ${start.y}`,
    `L ${sideX - corner * horizontalDirection} ${start.y}`,
    `Q ${sideX} ${start.y}, ${sideX} ${start.y + corner * verticalDirection}`,
    `L ${sideX} ${end.y - corner * verticalDirection}`,
    `Q ${sideX} ${end.y}, ${sideX - corner * horizontalDirection} ${end.y}`,
    `L ${end.x} ${end.y}`,
  ].join(" ");
}

function outgoingVisibleChildren(parent, nodes) {
  return nodes.filter((node) => !node.hidden && node.prerequisites.includes(parent.id));
}

function branchPath(parent, child, siblings = []) {
  const nodeOffset = 31;
  const corner = 16;
  const verticalDirection = child.displayY >= parent.displayY ? 1 : -1;
  const horizontalDirection = child.displayX >= parent.displayX ? 1 : -1;
  const startX = parent.displayX + nodeOffset * horizontalDirection;
  const startY = parent.displayY;
  const endX = child.displayX - nodeOffset * horizontalDirection;
  const endY = child.displayY;
  const sideSiblings = siblings.filter((node) => (node.displayX >= parent.displayX ? 1 : -1) === horizontalDirection);
  const nearestDistanceX = Math.min(
    ...sideSiblings.map((node) => Math.abs(node.displayX - parent.displayX)),
    Math.abs(child.displayX - parent.displayX),
  );
  const branchOffset = Math.max(56, Math.min(92, nearestDistanceX * 0.42));
  const branchX = parent.displayX + branchOffset * horizontalDirection;

  return [
    `M ${startX} ${startY}`,
    `L ${branchX - corner * horizontalDirection} ${startY}`,
    `Q ${branchX} ${startY}, ${branchX} ${startY + corner * verticalDirection}`,
    `L ${branchX} ${endY - corner * verticalDirection}`,
    `Q ${branchX} ${endY}, ${branchX + corner * horizontalDirection} ${endY}`,
    `L ${endX} ${endY}`,
  ].join(" ");
}

function pathFor(parent, child, nodes = []) {
  const nodeOffset = 31;
  const lead = 18;

  if (Math.abs(parent.displayX - child.displayX) < 8) {
    const direction = child.displayY >= parent.displayY ? 1 : -1;
    const verticalStartOffset = 28;
    const verticalEndOffset = 32;
    const startX = parent.displayX;
    const startY = parent.displayY + verticalStartOffset * direction;
    const endX = child.displayX;
    const endY = child.displayY - verticalEndOffset * direction;
    const midY = (startY + endY) / 2;
    if (edgeWouldCrossNode({ x: startX, y: startY }, { x: endX, y: endY }, parent, child, nodes)) {
      return sideRoutePath(parent, child, nodes);
    }
    return `M ${startX} ${startY} L ${startX} ${midY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${midY} L ${endX} ${endY}`;
  }

  const direction = child.displayX >= parent.displayX ? 1 : -1;
  const startX = parent.displayX + nodeOffset * direction;
  const startY = parent.displayY;
  const endX = child.displayX - nodeOffset * direction;
  const endY = child.displayY;
  const distanceX = Math.abs(endX - startX);
  const curve = Math.max(38, Math.min(130, distanceX * 0.42));
  const startLeadX = startX + lead * direction;
  const endLeadX = endX - lead * direction;
  const controlStartX = startX + curve * direction;
  const controlEndX = endX - curve * direction;
  const visibleChildren = outgoingVisibleChildren(parent, nodes);
  const fanOut = visibleChildren.length > 1;
  if (fanOut && Math.abs(parent.displayY - child.displayY) > 42) {
    return branchPath(parent, child, visibleChildren);
  }
  if (Math.abs(parent.displayY - child.displayY) > 80 && edgeWouldCrossNode({ x: startX, y: startY }, { x: endX, y: endY }, parent, child, nodes)) {
    return branchPath(parent, child, visibleChildren);
  }
  return `M ${startX} ${startY} L ${startLeadX} ${startY} C ${controlStartX} ${startY}, ${controlEndX} ${endY}, ${endLeadX} ${endY} L ${endX} ${endY}`;
}

function renderEdgeDefs() {
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  marker.setAttribute("id", "edge-arrow");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "8");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "5");
  marker.setAttribute("markerHeight", "5");
  marker.setAttribute("orient", "auto-start-reverse");
  const arrow = document.createElementNS("http://www.w3.org/2000/svg", "path");
  arrow.setAttribute("d", "M 1 1 L 9 5 L 1 9 z");
  arrow.classList.add("edge-arrow");
  marker.appendChild(arrow);
  defs.appendChild(marker);
  edgesSvg.appendChild(defs);
}

function tooltip(skill) {
  const missing = Object.entries(skill.missing || {});
  const prereqs = skill.prerequisites.length
    ? skill.prerequisites.map((id) => `${id}: ${skill.required_points}`).join(", ")
    : "None";
  const locked = skill.unlocked
    ? "Unlocked"
    : `Locked: ${missing.map(([id, amount]) => `${id} needs ${amount} more`).join(", ")}`;
  const description = escapeHtml(skill.description || "").replace(/\n/g, "<br>");
  return `
    <strong>${escapeHtml(skill.name)}</strong>
    <div class="tooltip-description">${description}</div>
    <div>Level: ${graphData.levels[skill.id] || 0}/${skill.max_level}</div>
    <div>Prerequisites: ${escapeHtml(prereqs)}</div>
    <div class="${skill.unlocked ? "" : "warn"}">${escapeHtml(locked)}</div>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function render() {
  const skills = graphData.skills || [];
  document.documentElement.style.setProperty("--accent", graphData.settings?.edge_color || "#5cc8ff");
  const { positioned, height, width } = layoutSkills();
  layoutMetrics = { width, height };
  const byId = positioned;
  lastRenderKey = renderKey(graphData);
  edgesSvg.innerHTML = "";
  nodesEl.innerHTML = "";
  renderEdgeDefs();

  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  edgesSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  applyScale();

  renderTreeHeaders();

  skills.forEach((child) => {
    child = byId.get(child.id);
    if (!child || child.hidden) return;
    child.prerequisites.forEach((parentId) => {
      const parent = byId.get(parentId);
      if (!parent || parent.hidden) return;
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.classList.add("edge", edgeStatus(parent, child));
      group.dataset.source = parent.id;
      group.dataset.target = child.id;

      const d = pathFor(parent, child, [...byId.values()]);
      const hit = document.createElementNS("http://www.w3.org/2000/svg", "path");
      hit.setAttribute("d", d);
      hit.classList.add("edge-hit");
      const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
      line.setAttribute("d", d);
      const rail = document.createElementNS("http://www.w3.org/2000/svg", "path");
      rail.setAttribute("d", d);
      rail.classList.add("edge-rail");
      line.classList.add("edge-line");
      line.setAttribute("marker-end", "url(#edge-arrow)");
      group.append(hit, rail, line);
      group.addEventListener("mouseenter", () => highlightEdge(group, true));
      group.addEventListener("mouseleave", () => highlightEdge(group, false));
      edgesSvg.appendChild(group);
    });
  });

  skills.forEach((skill) => {
    skill = byId.get(skill.id);
    if (!skill || skill.hidden) return;
    const level = graphData.levels[skill.id] || 0;
    const node = document.createElement("div");
    node.className = "skill-node";
    node.dataset.skillId = skill.id;
    node.style.left = `${skill.displayX}px`;
    node.style.top = `${skill.displayY}px`;
    node.classList.add(skill.unlocked ? "available" : "locked");
    if (graphData.settings?.show_skill_tooltips) node.classList.add("show-tooltip");
    if (level > 0) node.classList.add("invested");
    if (level >= skill.max_level) node.classList.add("maxed");
    const imageHtml = skill.icon_data_uri
      ? `<img alt="" src="${skill.icon_data_uri}" />`
      : `<span class="fallback-icon">${skill.name.slice(0, 1)}</span>`;
    node.innerHTML = `
      <div class="skill-name">${skill.name}</div>
      <div class="skill-icon">${imageHtml}</div>
      <div class="skill-level">${level}/${skill.max_level}</div>
      <div class="tooltip">${tooltip(skill)}</div>
    `;
    node.addEventListener("click", (event) => {
      event.preventDefault();
      if (event.ctrlKey) {
        openSkillDocs(skill);
        return;
      }
      highlightNode(skill.id, true);
      emit("increment", skill.id);
    });
    node.addEventListener("pointerdown", (event) => {
      if (event.button !== 2) return;
      event.preventDefault();
      event.stopPropagation();
      emit("decrement", skill.id);
    });
    node.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
    node.addEventListener("mouseenter", () => highlightNode(skill.id, true));
    node.addEventListener("mouseleave", () => highlightNode(skill.id, false));
    nodesEl.appendChild(node);
  });

  requestAnimationFrame(restoreViewportState);
}

function availableGraphWidth() {
  return Math.max(viewport.clientWidth || document.body.clientWidth || layoutMetrics.width || 320, 320);
}

function applyScale() {
  if (!layoutMetrics.width || !layoutMetrics.height) return;
  const availableWidth = availableGraphWidth();
  const fitScale = Math.min(1, availableWidth / layoutMetrics.width);
  canvas.style.transform = `scale(${fitScale})`;
  viewport.style.height = `${layoutMetrics.height * fitScale}px`;
  window.Streamlit.setFrameHeight(layoutMetrics.height * fitScale + 24);
  lastAvailableWidth = availableWidth;
}

function scheduleScaleUpdate() {
  if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(() => {
    resizeFrame = null;
    if (Math.abs(availableGraphWidth() - lastAvailableWidth) < 1) return;
    applyScale();
  });
}

function renderTreeHeaders() {
  const collapsed = (graphData.settings && graphData.settings.collapsed_trees) || {};
  let offsetY = 24;
  treeGroups().forEach(([treeName, skills]) => {
    const isCollapsed = collapsed[treeName] !== false;
    const localMaxY = Math.max(...skills.map((skill) => skill.y), 0);
    const panelHeight = isCollapsed ? 54 : localMaxY + 152;
    const panel = document.createElement("div");
    panel.className = "tree-panel";
    panel.style.top = `${offsetY - 8}px`;
    panel.style.height = `${panelHeight}px`;
    nodesEl.appendChild(panel);

    const header = document.createElement("div");
    header.className = "tree-header";
    header.draggable = true;
    header.dataset.tree = treeName;
    header.style.top = `${offsetY}px`;
    const spent = treeSpentPoints(skills);
    header.innerHTML = `
      <span class="tree-title">${treeName} Skills (${spent})</span>
      <div class="tree-actions">
        <button type="button" data-action="toggle">${isCollapsed ? "Expand" : "Collapse"}</button>
        <button type="button" data-action="reset">Reset</button>
      </div>
    `;
    header.addEventListener("click", () => {
      toggleTree(treeName);
    });
    header.querySelector('[data-action="toggle"]').addEventListener("click", (event) => {
      event.stopPropagation();
      toggleTree(treeName);
    });
    header.querySelector('[data-action="reset"]').addEventListener("click", (event) => {
      event.stopPropagation();
      emitTreeEvent("reset_tree", { tree: treeName });
    });
    header.addEventListener("dragstart", (event) => {
      header.classList.add("dragging-tree");
      event.dataTransfer.setData("text/plain", treeName);
      event.dataTransfer.effectAllowed = "move";
    });
    header.addEventListener("dragend", () => header.classList.remove("dragging-tree"));
    header.addEventListener("dragover", (event) => event.preventDefault());
    header.addEventListener("drop", (event) => {
      event.preventDefault();
      const dragged = event.dataTransfer.getData("text/plain");
      if (!dragged || dragged === treeName) return;
      const order = treeGroups().map(([name]) => name);
      const from = order.indexOf(dragged);
      const to = order.indexOf(treeName);
      order.splice(from, 1);
      order.splice(to, 0, dragged);
      emitTreeEvent("reorder_trees", { tree_order: order });
    });
    nodesEl.appendChild(header);
    offsetY += isCollapsed ? 68 : localMaxY + 170;
  });
}

function highlightNode(skillId, on) {
  if (!on) {
    clearHighlightedPaths();
    return;
  }
  showSkillPath(skillId);
}

function clearHighlightedPaths() {
  document.querySelectorAll(".edge.path").forEach((edge) => edge.classList.remove("path"));
}

function showSkillPath(skillId) {
  clearHighlightedPaths();
  ancestorEdges(skillId).forEach(([source, target]) => {
    const edge = document.querySelector(`.edge[data-source="${source}"][data-target="${target}"]`);
    if (!edge) return;
    edge.classList.add("path");
    edgesSvg.appendChild(edge);
  });
}

function highlightEdge(edge, on) {
  edge.classList.toggle("hover", on);
  if (on) edgesSvg.appendChild(edge);
  [edge.dataset.source, edge.dataset.target].forEach((id) => {
    const node = document.querySelector(`.skill-node[data-skill-id="${id}"]`);
    if (node) node.classList.toggle("edge-hover", on);
  });
}

viewport.addEventListener("contextmenu", (event) => {
  if (event.target.closest(".skill-node")) {
    event.preventDefault();
    event.stopPropagation();
  }
});
window.Streamlit.events.addEventListener(window.Streamlit.RENDER_EVENT, (event) => {
  const nextData = event.detail.args;
  const nextKey = renderKey(nextData);
  graphData = nextData;
  if (lastRenderKey === nextKey && nodesEl.childElementCount) {
    document.documentElement.style.setProperty("--accent", graphData.settings?.edge_color || "#5cc8ff");
    updateDynamicState();
    applyScale();
    return;
  }
  render();
});
new ResizeObserver(scheduleScaleUpdate).observe(viewport);
window.addEventListener("resize", scheduleScaleUpdate);
window.Streamlit.setComponentReady();
window.Streamlit.setFrameHeight(720);
