import { detailKeys, detailLabels, detailOptions } from "./property-details";
import type { PropertyDetails } from "./property-details";

export default function PropertyDetailFields({ value = {}, search = false }: { value?: PropertyDetails; search?: boolean }) {
  return <>{detailKeys.map(key => <label key={key}>{detailLabels[key]}
    {key === "neighborhood" ? <input name={key} maxLength={100} defaultValue={value[key] ?? ""} /> : key === "floor" ? <><input name={key} type="number" min={-2} max={200} step={1} defaultValue={value[key] ?? ""} /><small>0 = prizemlje; -1 i -2 = nivoi ispod prizemlja.</small></> : <select name={key} defaultValue={value[key] == null ? "" : String(value[key])}>
      <option value="">{search ? "Sve opcije" : "Nije navedeno"}</option>
      {key.startsWith("has_") ? <><option value="true">Da</option><option value="false">Ne</option></> : Object.entries(detailOptions[key as keyof typeof detailOptions]).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
    </select>}
  </label>)}</>;
}
