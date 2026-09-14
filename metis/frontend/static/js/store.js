export const state = {
  conversationId: null,
  messages: [],
  activeTask: null,
  results: [],
  selectedResult: null,
  preview: null,
  intervention: null,
  connection: "connecting",
  planningId: null,
  planningSource: null,
};

export function reset() {
  state.conversationId = null;
  state.messages = [];
  state.activeTask = null;
  state.results = [];
  state.selectedResult = null;
  state.preview = null;
  state.intervention = null;
}
