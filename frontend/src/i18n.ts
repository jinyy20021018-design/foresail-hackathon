export type Language = "en" | "zh";

const text: Record<Language, Record<string, string>> = {
  en: {
    switchLanguage: "中文",
    mvp: "MVP 1.0",
    appTitle: "ForeSail",
    createLead: "Create one case-aware shipment monitor for CAPEMOLLINI on the Shanghai to Chittagong to Dhaka route.",
    mockNoteStrong: "Mock extracted fields for MVP.",
    mockNoteBody: "Files are not parsed in this version.",
    createDemoCase: "Create Demo Case",
    creating: "Creating...",
    uploadCaseFiles: "Upload Case Files",
    optional: "Optional",
    caseLabel: "Case",
    dashboardTitle: "CAPEMOLLINI Trade Watch",
    startMonitoring: "Start Monitoring",
    monitoring: "Monitoring...",
    runAgentCycle: "Run Agent Monitoring Cycle",
    agentRunning: "Agent running...",
    monitoringActive: "Monitoring Active",
    continueMonitoring: "Continue Monitoring",
    agentRunSummary: "Agent Run Summary",
    agentSummaryEmpty: "Run the agent monitoring cycle to generate a summary.",
    agentRunComplete: "Agent Run Complete",
    llmAgent: "LLM Agent",
    summarySource: "Summary source",
    llm: "LLM",
    deterministic: "Deterministic",
    deterministic_fallback: "Deterministic fallback",
    llmRequired: "required",
    agentRunTrace: "Agent Run Trace",
    agentTraceEmpty: "Agent trace will appear after the monitoring cycle runs.",
    eventsScanned: "events scanned",
    exposureCategories: "exposure categories",
    actionsGenerated: "actions generated",
    steps: "steps",
    caseSnapshot: "Case Snapshot",
    watchProfile: "Case Watch Profile",
    statusTimeline: "Status Timeline",
    eventResults: "Event Relevance Results",
    riskSummary: "Risk Trigger / Exposure Summary",
    actionBoard: "Recommended Action Board",
    evaluated: "evaluated",
    actions: "actions",
    noRiskSummary: "No risk summary yet.",
    noActions: "Actions will be generated after relevant exposures are found.",
    runMonitoringHint: "Run Start Monitoring to classify the configured external event feed.",
    triggered: "Triggered",
    noTrigger: "No trigger",
    triggerEvents: "Trigger events",
    watchEventsConsidered: "Watch events considered",
    evidence: "Evidence",
    triggerEvidence: "Trigger evidence",
    watchEvidence: "Watch evidence",
    none: "None",
    status: "Status",
    vessel: "Vessel",
    route: "Route",
    portOfLoading: "Port of Loading",
    portOfDischarge: "Port of Discharge",
    finalDestination: "Final Destination",
    etd: "ETD",
    eta: "ETA",
    latestShipmentDate: "Latest Shipment Date",
    paymentMethod: "Payment Method",
    incoterm: "Incoterm",
    uploadedFileNames: "Uploaded file names",
    watchedVessel: "Vessel",
    watchedPorts: "Ports",
    routeRegions: "Route regions",
    riskCategories: "Risk categories",
    eventTitle: "Event title",
    classification: "Classification",
    score: "Score",
    matchedFactors: "Matched factors",
    explanation: "Explanation",
    mappedExposures: "Mapped exposures",
    owner: "Owner",
    priority: "Priority",
    deadline: "Deadline",
    exposure: "Exposure",
    failedCreate: "Failed to create demo case.",
    failedProfile: "Failed to load watch profile.",
    failedTimeline: "Failed to load status timeline.",
    failedMonitor: "Failed to run monitoring cycle.",
    failedContinue: "Failed to continue monitoring."
  },
  zh: {
    switchLanguage: "English",
    mvp: "MVP 1.0",
    appTitle: "ForeSail",
    createLead: "为 CAPEMOLLINI 的上海至吉大港再至达卡航线创建一个交易级监控 Case。",
    mockNoteStrong: "MVP 使用模拟抽取字段。",
    mockNoteBody: "当前版本不会解析上传文件内容。",
    createDemoCase: "创建演示 Case",
    creating: "创建中...",
    uploadCaseFiles: "上传 Case 文件",
    optional: "可选",
    caseLabel: "Case",
    dashboardTitle: "CAPEMOLLINI 交易监控",
    startMonitoring: "开始监控",
    monitoring: "监控中...",
    runAgentCycle: "运行 Agent 监控周期",
    agentRunning: "Agent 运行中...",
    monitoringActive: "持续监控中",
    continueMonitoring: "继续监控",
    agentRunSummary: "Agent 运行总结",
    agentSummaryEmpty: "运行 Agent 监控周期后会生成总结。",
    agentRunComplete: "Agent 运行完成",
    llmAgent: "LLM Agent",
    summarySource: "总结来源",
    llm: "LLM",
    deterministic: "确定性规则",
    deterministic_fallback: "确定性 fallback",
    llmRequired: "强制启用",
    agentRunTrace: "Agent 运行轨迹",
    agentTraceEmpty: "运行监控周期后会显示 Agent 执行轨迹。",
    eventsScanned: "条事件已扫描",
    exposureCategories: "个敞口类别",
    actionsGenerated: "个行动已生成",
    steps: "个步骤",
    caseSnapshot: "Case 快照",
    watchProfile: "Case 监控画像",
    statusTimeline: "状态时间线",
    eventResults: "事件相关性结果",
    riskSummary: "风险触发 / 敞口总结",
    actionBoard: "推荐行动板",
    evaluated: "条已评估",
    actions: "个行动",
    noRiskSummary: "暂无风险总结。",
    noActions: "发现相关敞口后会生成推荐行动。",
    runMonitoringHint: "点击“开始监控”以分类已配置的外部事件流。",
    triggered: "已触发",
    noTrigger: "未触发",
    triggerEvents: "触发事件",
    watchEventsConsidered: "观察事件",
    evidence: "证据",
    triggerEvidence: "触发证据",
    watchEvidence: "观察证据",
    none: "无",
    status: "状态",
    vessel: "船舶",
    route: "路线",
    portOfLoading: "装港",
    portOfDischarge: "卸港",
    finalDestination: "最终目的地",
    etd: "预计离港",
    eta: "预计到港",
    latestShipmentDate: "最迟装运日",
    paymentMethod: "付款方式",
    incoterm: "贸易术语",
    uploadedFileNames: "已上传文件名",
    watchedVessel: "监控船舶",
    watchedPorts: "监控港口",
    routeRegions: "航线区域",
    riskCategories: "风险类别",
    eventTitle: "事件标题",
    classification: "分类",
    score: "分数",
    matchedFactors: "匹配因素",
    explanation: "解释",
    mappedExposures: "映射敞口",
    owner: "负责人",
    priority: "优先级",
    deadline: "截止时间",
    exposure: "敞口",
    failedCreate: "创建演示 Case 失败。",
    failedProfile: "加载监控画像失败。",
    failedTimeline: "加载状态时间线失败。",
    failedMonitor: "执行监控周期失败。",
    failedContinue: "继续监控失败。"
  }
};

const statuses: Record<string, string> = {
  DRAFT: "草稿",
  ACTIVE: "已激活",
  WATCHING: "监控中",
  AT_RISK: "存在风险",
  ACTION_REQUIRED: "需要行动",
  MONITORING: "持续监控"
};

const classifications: Record<string, string> = {
  Relevant: "相关",
  Watch: "观察",
  Irrelevant: "无关"
};

const factors: Record<string, string> = {
  vessel_match: "船名匹配",
  watched_port_match: "监控港口匹配",
  route_region_match: "航线区域匹配",
  unrelated_region: "无关区域",
  unrelated_port: "无关港口",
  shipment_window_overlap: "运输窗口重叠",
  eta_or_deadline_impact: "影响 ETA 或截止日",
  high_severity: "高严重度",
  weather_watch_cap: "天气观察上限"
};

const exposures: Record<string, string> = {
  Shipping: "运输",
  "LC Deadline": "信用证截止日",
  "Port Operation": "港口作业",
  "Payment Timeline": "付款时间线"
};

const severity: Record<string, string> = {
  High: "高",
  Medium: "中",
  Low: "低"
};

const owners: Record<string, string> = {
  Logistics: "物流",
  "Trade Finance": "贸易融资",
  "Freight Forwarder": "货代",
  Finance: "财务"
};

const deadlines: Record<string, string> = {
  Today: "今天",
  "T+1": "T+1"
};

const actions: Record<string, string> = {
  "Contact carrier to confirm latest ETA and delay reason": "联系承运人确认最新 ETA 和延误原因",
  "Request alternative routing or discharge options": "询问替代航线或卸货方案",
  "Review whether delay affects latest shipment date or document presentation": "复核延误是否影响最迟装运日或交单时点",
  "Prepare LC amendment request if shipment timing becomes non-compliant": "如装运时间可能不符，准备信用证修改申请",
  "Check Bangladesh / Chittagong port operation status": "检查孟加拉 / 吉大港港口作业状态",
  "Ask freight forwarder for congestion and discharge alternatives": "向货代询问拥堵情况和替代卸货方案",
  "Update expected payment and cashflow timeline": "更新预计付款和现金流时间线",
  "Notify finance team of possible working capital impact": "通知财务团队可能的营运资金影响"
};

const eventTitles: Record<string, string> = {
  "CAPEMOLLINI ETA delayed by 5 days": "CAPEMOLLINI ETA 延误 5 天",
  "Bangladesh port strike": "孟加拉港口罢工",
  "Typhoon near East China Sea": "东海附近台风",
  "Red Sea security incident": "红海安全事件",
  "Rotterdam port congestion": "鹿特丹港口拥堵"
};

const impacts: Record<string, string> = {
  "Shipment timing or routing may be disrupted.": "装运时间或航线可能受影响。",
  "Delay may create latest shipment or presentation timing risk under the LC.": "延误可能导致信用证下的最迟装运日或交单时点风险。",
  "Port disruption may slow discharge or inland delivery.": "港口中断可能拖慢卸货或内陆交付。",
  "ETA or discharge delay may shift expected payment and cashflow timing.": "ETA 或卸货延误可能改变预计付款和现金流时间。"
};

const rules: Record<string, string> = {
  "Alert if vessel delay is greater than or equal to 3 days": "船舶延误大于或等于 3 天时预警",
  "Alert if affected port matches port of loading or port of discharge": "受影响港口匹配装港或卸港时预警",
  "Alert if affected region overlaps the route corridor": "受影响区域与航线走廊重叠时预警",
  "Alert if event may affect latest shipment date or ETA": "事件可能影响最迟装运日或 ETA 时预警",
  "Filter out events in unrelated regions or unrelated ports": "过滤无关区域或无关港口事件"
};

const timelineReasons: Record<string, string> = {
  "Demo case initialized from built-in mock extracted fields.": "演示 Case 已基于内置模拟抽取字段初始化。",
  "Core trade fields are available.": "核心交易字段已具备。",
  "Monitoring started with configured external event feed.": "已使用已配置的外部事件流开始监控。",
  "At least one Relevant event was detected.": "检测到至少一个相关事件。",
  "Recommended actions were generated for the triggered exposures.": "已针对触发的敞口生成推荐行动。",
  "User confirmed the action board and continued monitoring.": "用户已确认行动板并继续监控。"
};

export function t(language: Language, key: string): string {
  return text[language][key] ?? text.en[key] ?? key;
}

export function display(language: Language, value: string, dictionary: Record<string, string>): string {
  return language === "zh" ? dictionary[value] ?? value : value;
}

export const translate = {
  status: (language: Language, value: string) => display(language, value, statuses),
  classification: (language: Language, value: string) => display(language, value, classifications),
  factor: (language: Language, value: string) => display(language, value, factors),
  exposure: (language: Language, value: string) => display(language, value, exposures),
  severity: (language: Language, value: string) => display(language, value, severity),
  owner: (language: Language, value: string) => display(language, value, owners),
  deadline: (language: Language, value: string) => display(language, value, deadlines),
  action: (language: Language, value: string) => display(language, value, actions),
  eventTitle: (language: Language, value: string) => display(language, value, eventTitles),
  impact: (language: Language, value: string) => display(language, value, impacts),
  rule: (language: Language, value: string) => display(language, value, rules),
  timelineReason: (language: Language, value: string) => display(language, value, timelineReasons)
};
