import { useId } from "react";
import { Icon } from "./Icon";

export function ProtocolEditor({
  busy,
  error,
  onChange,
  onClose,
  onLoadSample,
  onSubmit,
  open,
  value,
}: {
  busy: boolean;
  error: string | null;
  onChange: (value: string) => void;
  onClose: () => void;
  onLoadSample: () => void;
  onSubmit: () => void;
  open: boolean;
  value: string;
}) {
  const editorId = useId();
  if (!open) return null;

  return (
    <div className="ar-editor-layer" role="presentation">
      <button aria-label="Close protocol editor" className="ar-editor-scrim" onClick={onClose} type="button" />
      <aside aria-labelledby={`${editorId}-title`} aria-modal="true" className="ar-editor" role="dialog">
        <header>
          <div>
            <span>CALLER-SUPPLIED PUBLIC STATE</span>
            <h2 id={`${editorId}-title`}>Apply Revision Protocol Editor</h2>
          </div>
          <button aria-label="Close protocol editor" disabled={busy} onClick={onClose} type="button">
            <Icon name="close" size={18} />
          </button>
        </header>

        <p>
          Edit or paste one complete <code>v0.6.2.5</code> request. The backend validates the same
          fail-closed schema used by the runtime. Caller semantics remain unverified.
        </p>

        <div className="ar-editor-toolbar">
          <button disabled={busy} onClick={onLoadSample} type="button">Load valid sample</button>
          <span>No provider call until Apply is pressed</span>
        </div>

        <label htmlFor={`${editorId}-input`}>Request JSON</label>
        <textarea
          autoCapitalize="off"
          autoCorrect="off"
          id={`${editorId}-input`}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Load the protocol sample, then edit its public evidence, event, state, and closure candidates."
          spellCheck={false}
          value={value}
        />

        {error ? <p className="ar-editor-error" role="alert">{error}</p> : null}

        <footer>
          <span>Gradient stops at the public control map.</span>
          <button disabled={busy || value.trim().length === 0} onClick={onSubmit} type="button">
            {busy ? "Applying…" : "Apply JSON → Regenerate"}
          </button>
        </footer>
      </aside>
    </div>
  );
}
