type Props = {
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  fileName?: string | null;
  onChange: (files: FileList | null) => void;
};

export function FilePicker({ accept, multiple, disabled, fileName, onChange }: Props) {
  return (
    <label className={disabled ? "file-picker disabled" : "file-picker"}>
      <input
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        onChange={(event) => onChange(event.target.files)}
      />
      <span className="file-picker-button">Choose file{multiple ? "s" : ""}</span>
      <span className="file-picker-name">{fileName || "No file selected"}</span>
    </label>
  );
}
