(() => {
  async function readStream(response, onProgress) {
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `Simulation request failed (${response.status}).`);
    }
    if (!response.body) throw new Error('Live simulation progress is unavailable. Reload before trying again.');
    const reader = response.body.getReader(), decoder = new TextDecoder();
    let buffer = '', result, finished = false;
    async function consume(line) {
      if (!line.trim()) return;
      const message = JSON.parse(line);
      if (finished) throw new Error('Unexpected data after simulation completion.');
      if (message.type === 'error') throw new Error(message.error || 'Simulation failed.');
      if (message.type === 'progress') await onProgress(message.event);
      else if (message.type === 'result') { result = message.result; finished = true; }
      else throw new Error('Unknown simulation progress message.');
    }
    try {
      while (true) {
        const {value, done} = await reader.read();
        buffer += decoder.decode(value, {stream:!done});
        if (buffer.length > 16 * 1024 * 1024) throw new Error('Simulation response exceeded the display limit.');
        let end;
        while ((end = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0,end); buffer = buffer.slice(end+1);
          await consume(line);
        }
        if (done) { if (buffer.trim()) await consume(buffer); break; }
      }
    } finally { reader.releaseLock(); }
    if (!finished) throw new Error('Simulation connection closed before confirmation. Reload the save before simulating again.');
    return result;
  }

  function lotteryRevealState(lottery, count) {
    const sequence = [...(lottery.reveal || [])].sort((a,b)=>Number(b.pick)-Number(a.pick));
    const revealed = sequence.slice(0,Math.max(0,count));
    const promoted = new Set(), remaining = new Map((lottery.odds || []).map(row=>[row.team.id,row]));
    // "Promoted" (a team that jumped into the four drawn picks) only means something in the old format; under
    // the 3-2-1 lottery every pick is drawn.
    if (lottery.format !== "3-2-1" && Number(lottery.draw_count) > 0) for (const row of revealed) {
      const id = row.original_team?.id;
      remaining.delete(id);
      if (Number(row.pick) > 4 && Number(row.starting_seed) > 0) {
        for (const [candidate, entry] of remaining) {
          if (Number(entry.seed) > Number(row.starting_seed)) promoted.add(candidate);
        }
      } else if (Number(row.pick) <= 4) promoted.add(id);
    }
    return {revealed, promoted:[...promoted], complete:revealed.length===sequence.length,
      nextPick:sequence[revealed.length]?.pick ?? null, total:sequence.length};
  }

  function draftPlaybackFrame(finalRoom, presentationEvents, revealedPickCount) {
    const room = finalRoom || {};
    const picks = (presentationEvents || []).filter(event => event?.type === 'pick');
    const timeline = (room.draft_timeline || []).map(row => ({...row, selection:{...(row.selection || {})}}));
    const finalIndex = Number(room.state?.current_index || 0);
    const startIndex = Math.max(0, finalIndex - picks.length);
    const revealed = Math.max(0, Math.min(picks.length, Number(revealedPickCount) || 0));
    const currentIndex = Math.min(timeline.length, startIndex + revealed);
    timeline.forEach((row,index) => {
      row.draft_status = index < currentIndex ? 'selected' : index === currentIndex ? 'current' : 'upcoming';
    });
    const current = timeline[currentIndex] || null;
    const userTeamId = room.team?.id;
    const nextUser = timeline.slice(currentIndex).find(row => row.team?.id === userTeamId) || null;
    const revealedIds = new Set(picks.slice(0,revealed).map(event => String(event.prospect?.id || '')));
    const pendingIds = new Set(picks.slice(revealed).map(event => String(event.prospect?.id || '')));
    const entries = (room.draft_board?.entries || []).map(entry => {
      const prospect = entry.prospect || entry;
      const id = String(prospect.id || prospect.prospect_id || entry.prospect_id || '');
      if (pendingIds.has(id)) return {...entry, draft_status:'available', selected_pick:null, selected_team:null};
      if (revealedIds.has(id)) {
        const event = picks.slice(0,revealed).find(row => String(row.prospect?.id || '') === id);
        return {...entry, draft_status:'drafted', selected_pick:event?.overall_pick, selected_team:event?.team?.abbrev || event?.team?.id};
      }
      return entry;
    });
    const isComplete = currentIndex >= timeline.length;
    return {
      ...room,
      state:{...(room.state || {}), current_index:currentIndex, status:isComplete?'completed':'in_progress'},
      current_selection:current,
      current_pick_is_user_owned:Boolean(current && current.team?.id === userTeamId),
      next_user_selection:nextUser,
      previous_picks:timeline.slice(0,currentIndex),
      upcoming:timeline.slice(currentIndex),
      upcoming_order:timeline.slice(currentIndex),
      draft_timeline:timeline,
      draft_board:{...(room.draft_board || {}), entries},
    };
  }

  const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false;
  const wait = ms => new Promise(resolve=>setTimeout(resolve,ms));
  window.GameSimulation = Object.freeze({readStream, lotteryRevealState, draftPlaybackFrame, reducedMotion, wait});
})();
