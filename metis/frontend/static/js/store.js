export const state = {
  conversationId: null,
  messages: [],
  activeTask: null,
  results: [],
  selectedResult: null,
  preview: null,
  intervention: null,
  interventions: [],
  connection: "connecting",
  polling: null,
  sending: false,
  ws: null,
};

const CID_KEY = "metis.conversation_id";

export function loadSavedConversationId() {
  try { return localStorage.getItem(CID_KEY); } catch { return null; }
}

export function saveConversationId(cid) {
  state.conversationId = cid;
  try { localStorage.setItem(CID_KEY, cid); } catch { /* private mode */ }
}

export function reset() {
  state.conversationId = null;
  state.messages = [];
  state.activeTask = null;
  state.results = [];
  state.selectedResult = null;
  state.preview = null;
  state.intervention = null;
  try { localStorage.removeItem(CID_KEY); } catch { /* noop */ }
}
