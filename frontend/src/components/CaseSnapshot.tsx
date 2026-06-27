import type { TradeCase } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = {
  tradeCase: TradeCase;
  language: Language;
};

export function CaseSnapshot({ tradeCase, language }: Props) {
  const fields = [
    [t(language, "status"), translate.status(language, tradeCase.status)],
    [t(language, "vessel"), tradeCase.vessel],
    [t(language, "route"), tradeCase.route],
    [t(language, "portOfLoading"), tradeCase.port_of_loading],
    [t(language, "portOfDischarge"), tradeCase.port_of_discharge],
    [t(language, "finalDestination"), tradeCase.final_destination],
    [t(language, "etd"), tradeCase.etd],
    [t(language, "eta"), tradeCase.eta],
    [t(language, "latestShipmentDate"), tradeCase.latest_shipment_date],
    [t(language, "paymentMethod"), tradeCase.payment_method],
    [t(language, "incoterm"), tradeCase.incoterm]
  ];

  return (
    <section className="panel case-snapshot-panel">
      <div className="panel-heading">
        <h2>{t(language, "caseSnapshot")}</h2>
        <span className={`status-pill status-${tradeCase.status.toLowerCase()}`}>
          {translate.status(language, tradeCase.status)}
        </span>
      </div>
      <dl className="field-grid">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {tradeCase.uploaded_files && tradeCase.uploaded_files.length > 0 && (
        <p className="subtle">
          {t(language, "uploadedFileNames")}: {tradeCase.uploaded_files.join(", ")}
        </p>
      )}
    </section>
  );
}
