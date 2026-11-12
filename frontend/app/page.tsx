"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Cpu,
  Database,
  ExternalLink,
  Flame,
  Gauge,
  HelpCircle,
  Layers,
  LayoutDashboard,
  Menu,
  Play,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ScatterChart,
  Scatter,
  ReferenceLine,
} from "recharts";

import {
  api,
  DatasetVersion,
  EngineDetail,
  EngineRunSummary,
  EngineCycleData,
  FleetSummary,
  ModelVersion,
  EvaluationRun,
} from "../lib/api";

type TabType = "overview" | "engines" | "datasets" | "models";

const RISK_BADGES = {
  healthy: "bg-emerald-50 text-emerald-700 border-emerald-200",
  planning: "bg-sky-50 text-sky-700 border-sky-200",
  attention: "bg-amber-50 text-amber-800 border-amber-200",
  urgent: "bg-rose-50 text-rose-700 border-rose-200",
};

export default function TelemetryXDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [isLoading, setIsLoading] = useState(false);
  const [isDemoRunning, setIsDemoRunning] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");

  // Core Data States
  const [fleetSummary, setFleetSummary] = useState<FleetSummary | null>(null);
  const [datasets, setDatasets] = useState<DatasetVersion[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [engines, setEngines] = useState<EngineRunSummary[]>([]);
  const [selectedEngineId, setSelectedEngineId] = useState<string | null>(null);
  const [engineDetail, setEngineDetail] = useState<EngineDetail | null>(null);
  const [engineCycles, setEngineCycles] = useState<EngineCycleData[]>([]);
  const [models, setModels] = useState<ModelVersion[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationRun[]>([]);

  // Engine Picker State
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [pickerSearch, setPickerSearch] = useState("");
  const [pickerFilterRisk, setPickerFilterRisk] = useState("all");
  const pickerRef = useRef<HTMLDivElement>(null);

  // Selected sensor for the engine time-series chart
  const [selectedSensor, setSelectedSensor] = useState<string>("sensor_3"); // T30 HPC outlet temperature

  // Filter state for engines table in Dataset tab
  const [searchUnit, setSearchUnit] = useState<string>("");
  const [filterRisk, setFilterRisk] = useState<string>("all");

  // Load Initial Dashboard Data
  const refreshAll = async () => {
    setIsLoading(true);
    try {
      const summary = await api.getFleetSummary().catch(() => null);
      if (summary) setFleetSummary(summary);

      const dsList = await api.getDatasets().catch(() => []);
      setDatasets(dsList);

      const activeDs = selectedDatasetId || (dsList.length > 0 ? dsList[0].id : null);
      if (activeDs) {
        setSelectedDatasetId(activeDs);
        const engList = await api.getDatasetEngines(activeDs).catch(() => []);
        setEngines(engList);
        if (engList.length > 0 && !selectedEngineId) {
          setSelectedEngineId(engList[0].id);
        }
      }

      const modelList = await api.getModels().catch(() => []);
      setModels(modelList);

      const evalList = await api.getEvaluations().catch(() => []);
      setEvaluations(evalList);
    } catch (err: any) {
      console.error("Refresh error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshAll();
  }, []);

  // When selectedEngineId changes, fetch engine details & cycle telemetry
  useEffect(() => {
    if (!selectedEngineId) return;

    api
      .getEngineDetail(selectedEngineId)
      .then((detail) => setEngineDetail(detail))
      .catch((err) => console.error("Engine detail fetch error:", err));

    api
      .getEngineCycles(selectedEngineId, 1, 250)
      .then((cycles) => setEngineCycles(cycles))
      .catch((err) => console.error("Engine cycles fetch error:", err));
  }, [selectedEngineId]);

  // Click outside to close custom engine picker popover
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(event.target as Node)) {
        setIsPickerOpen(false);
      }
    }
    if (isPickerOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isPickerOpen]);

  // When selectedDatasetId changes, load its engines
  const handleDatasetChange = async (dsId: string) => {
    setSelectedDatasetId(dsId);
    try {
      const engList = await api.getDatasetEngines(dsId);
      setEngines(engList);
      if (engList.length > 0) {
        setSelectedEngineId(engList[0].id);
      } else {
        setSelectedEngineId(null);
        setEngineDetail(null);
        setEngineCycles([]);
      }
    } catch (err) {
      console.error("Dataset change error:", err);
    }
  };

  // Run One-Click Interactive Demo Pipeline
  const runOneClickDemo = async () => {
    setIsDemoRunning(true);
    setFeedbackMsg("Ingesting NASA C-MAPSS FD001 raw datasets...");
    try {
      const sampleRes = await api.loadSampleDataset();
      const dsId = sampleRes.dataset_id;
      setSelectedDatasetId(dsId);
      setFeedbackMsg("Training Quantile Gradient Boosting RUL regressor...");

      const expRes = await api.runExperiment({
        dataset_version_id: dsId,
        name: "fd001-gradient-boosting-demo",
        hyperparameters: { learning_rate: 0.08, max_iter: 50, max_depth: 6 },
        rul_cap: 125,
      });

      setFeedbackMsg("Computing batch RUL predictions, confidence bounds, and SHAP attributions...");
      await api.runPredictions(expRes.model_version_id, dsId, "test");

      setFeedbackMsg("Mission telemetry hydrated and ready for inspection.");
      await refreshAll();
      setTimeout(() => setFeedbackMsg(null), 4000);
    } catch (err: any) {
      setFeedbackMsg(`Demo execution error: ${err.message}`);
    } finally {
      setIsDemoRunning(false);
    }
  };

  // Current active engine
  const currentEngine = useMemo(() => {
    return engines.find((e) => e.id === selectedEngineId) || null;
  }, [engines, selectedEngineId]);

  // Step through engines sequentially
  const handlePrevUnit = () => {
    if (engines.length === 0) return;
    const currentIndex = engines.findIndex((e) => e.id === selectedEngineId);
    const prevIndex = currentIndex <= 0 ? engines.length - 1 : currentIndex - 1;
    setSelectedEngineId(engines[prevIndex].id);
  };

  const handleNextUnit = () => {
    if (engines.length === 0) return;
    const currentIndex = engines.findIndex((e) => e.id === selectedEngineId);
    const nextIndex = currentIndex >= engines.length - 1 ? 0 : currentIndex + 1;
    setSelectedEngineId(engines[nextIndex].id);
  };

  // Sorted Priority Action Units (urgent & attention first, lowest RUL first)
  const priorityUnits = useMemo(() => {
    if (engines.length === 0) return [];
    const riskRank = { urgent: 0, attention: 1, planning: 2, healthy: 3 };
    return [...engines].sort((a, b) => {
      const rankA = a.risk_level ? riskRank[a.risk_level] ?? 4 : 4;
      const rankB = b.risk_level ? riskRank[b.risk_level] ?? 4 : 4;
      if (rankA !== rankB) return rankA - rankB;
      return (a.predicted_rul ?? 999) - (b.predicted_rul ?? 999);
    });
  }, [engines]);

  // Filtered engines for the custom popover picker
  const pickerFilteredUnits = useMemo(() => {
    return engines.filter((e) => {
      const q = pickerSearch.trim().toLowerCase();
      const matchesQuery =
        !q ||
        e.unit_number.toString().includes(q.replace(/[^0-9]/g, "")) ||
        e.file_role.toLowerCase().includes(q) ||
        e.risk_level?.toLowerCase().includes(q);

      let matchesCategory = true;
      if (pickerFilterRisk === "urgent") matchesCategory = e.risk_level === "urgent";
      else if (pickerFilterRisk === "attention") matchesCategory = e.risk_level === "attention";
      else if (pickerFilterRisk === "planning") matchesCategory = e.risk_level === "planning";
      else if (pickerFilterRisk === "healthy") matchesCategory = e.risk_level === "healthy";
      else if (pickerFilterRisk === "test") matchesCategory = e.file_role === "test";
      else if (pickerFilterRisk === "train") matchesCategory = e.file_role === "train";

      return matchesQuery && matchesCategory;
    });
  }, [engines, pickerSearch, pickerFilterRisk]);

  // Filtered engines for dataset tab directory table
  const filteredEngines = useMemo(() => {
    return engines.filter((e) => {
      const effectiveSearch = searchUnit || globalSearch;
      const matchesUnit = effectiveSearch
        ? e.unit_number.toString().includes(effectiveSearch.replace(/[^0-9]/g, "")) ||
          e.risk_level?.toLowerCase().includes(effectiveSearch.toLowerCase())
        : true;
      const matchesRisk = filterRisk === "all" ? true : e.risk_level === filterRisk;
      return matchesUnit && matchesRisk;
    });
  }, [engines, searchUnit, filterRisk, globalSearch]);

  // Formatted sensor time-series data for charting
  const chartData = useMemo(() => {
    if (!engineCycles || engineCycles.length === 0) return [];
    return engineCycles.map((c) => ({
      cycle: c.cycle,
      value: c.sensor_values ? c.sensor_values[selectedSensor] : null,
      setting1: c.operational_settings ? c.operational_settings[0] : 0,
    }));
  }, [engineCycles, selectedSensor]);

  // Scatter data for actual vs predicted RUL
  const evaluationScatterData = useMemo(() => {
    if (!evaluations || evaluations.length === 0) return [];
    const latestTest = evaluations.find((e) => e.evaluation_role === "test");
    if (!latestTest || !latestTest.metrics.per_unit_results) return [];

    return latestTest.metrics.per_unit_results.map((r) => ({
      unit: r.unit_number,
      actual: r.actual_rul,
      predicted: r.predicted_rul,
      absError: r.abs_error,
    }));
  }, [evaluations]);

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-800 flex flex-col md:flex-row antialiased selection:bg-slate-200">
      
      {/* MOBILE BACKDROP */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-xs md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 1. LEFT SIDEBAR NAVIGATION */}
      <aside
        className={`fixed md:sticky top-0 z-50 h-screen w-64 bg-white border-r border-slate-200 flex flex-col justify-between shrink-0 transition-transform duration-200 ease-in-out ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex flex-col flex-1 overflow-y-auto">
          {/* Header Brand */}
          <div className="h-16 px-5 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-white shadow-xs">
                <Gauge className="w-4 h-4 text-sky-400" />
              </div>
              <div>
                <h1 className="font-bold text-base text-slate-900 tracking-tight leading-tight">
                  TelemetryX
                </h1>
                <span className="text-[10px] font-semibold text-slate-400 tracking-wide uppercase">
                  NASA C-MAPSS FD001
                </span>
              </div>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1 rounded-md text-slate-400 hover:text-slate-600 md:hidden"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Demo Action Trigger */}
          <div className="p-3.5">
            <button
              onClick={runOneClickDemo}
              disabled={isDemoRunning}
              className="w-full flex items-center justify-center gap-2 px-3.5 py-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs shadow-xs transition-colors cursor-pointer disabled:opacity-60"
            >
              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
              <span>{isDemoRunning ? "Running Simulation..." : "Quick Demo Setup"}</span>
            </button>
          </div>

          {/* Main Navigation Group */}
          <div className="px-3 space-y-4">
            <div>
              <div className="px-3 pb-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Mission Operations
              </div>
              <nav className="space-y-0.5">
                {[
                  { id: "overview", label: "Fleet Overview", icon: LayoutDashboard },
                  { id: "engines", label: "Engine Inspector", icon: Gauge },
                ].map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => {
                        setActiveTab(tab.id as TabType);
                        setSidebarOpen(false);
                      }}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left cursor-pointer ${
                        isActive
                          ? "bg-slate-100 text-slate-900 font-semibold"
                          : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                      }`}
                    >
                      <Icon
                        className={`w-4 h-4 ${
                          isActive ? "text-slate-900" : "text-slate-400"
                        }`}
                      />
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </nav>
            </div>

            <div>
              <div className="px-3 pb-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Engineering & ML
              </div>
              <nav className="space-y-0.5">
                {[
                  { id: "datasets", label: "Dataset Explorer", icon: Database },
                  { id: "models", label: "Model Registry", icon: BarChart3 },
                ].map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => {
                        setActiveTab(tab.id as TabType);
                        setSidebarOpen(false);
                      }}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left cursor-pointer ${
                        isActive
                          ? "bg-slate-100 text-slate-900 font-semibold"
                          : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                      }`}
                    >
                      <Icon
                        className={`w-4 h-4 ${
                          isActive ? "text-slate-900" : "text-slate-400"
                        }`}
                      />
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Quick Priority Action Units in Sidebar */}
            {priorityUnits.length > 0 && (
              <div>
                <div className="px-3 pb-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Priority Units</span>
                  <span className="text-[9px] font-mono text-rose-600 font-bold">Action Needed</span>
                </div>
                <div className="space-y-1">
                  {priorityUnits.slice(0, 5).map((u) => {
                    const isUrgent = u.risk_level === "urgent";
                    const isAttention = u.risk_level === "attention";
                    return (
                      <button
                        key={u.id}
                        onClick={() => {
                          setSelectedEngineId(u.id);
                          setActiveTab("engines");
                          setSidebarOpen(false);
                        }}
                        className={`w-full flex items-center justify-between px-3 py-1.5 rounded-md text-xs transition-colors cursor-pointer text-left ${
                          selectedEngineId === u.id
                            ? "bg-slate-900 text-white font-semibold"
                            : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              isUrgent
                                ? "bg-rose-500"
                                : isAttention
                                ? "bg-amber-500"
                                : "bg-emerald-500"
                            }`}
                          />
                          <span className="font-mono text-xs font-medium">Unit #{u.unit_number}</span>
                        </div>
                        <span
                          className={`text-[11px] font-mono ${
                            selectedEngineId === u.id ? "text-slate-300" : "text-slate-500"
                          }`}
                        >
                          {u.predicted_rul !== null ? `${u.predicted_rul} cyc` : "—"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar Footer Status */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/60">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="font-medium text-slate-700">API Operational</span>
            </div>
            <span className="text-[11px] font-mono text-slate-400">v0.2.0</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
            <span>Turbofans</span>
            <span className="font-mono text-slate-600 font-semibold">{engines.length || 100} units</span>
          </div>
        </div>
      </aside>

      {/* 2. MAIN APPLICATION CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 px-4 sm:px-8 flex items-center justify-between gap-4 sticky top-0 z-30">
          <div className="flex items-center gap-3 flex-1 max-w-xl">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-100 md:hidden"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Quick Search */}
            <div className="relative w-full">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={globalSearch}
                onChange={(e) => setGlobalSearch(e.target.value)}
                placeholder="Search engine units (e.g. Unit 49), risk levels, models..."
                className="w-full pl-9 pr-4 py-1.5 bg-slate-50 hover:bg-slate-100/70 focus:bg-white rounded-lg text-xs text-slate-900 placeholder:text-slate-400 border border-slate-200 focus:border-slate-400 focus:outline-none transition-colors"
              />
            </div>
          </div>

          {/* Right Header Indicators */}
          <div className="flex items-center gap-3">
            <button
              onClick={refreshAll}
              disabled={isLoading}
              title="Refresh telemetry"
              className="p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-slate-700" : ""}`} />
            </button>

            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 text-xs font-medium border border-slate-200">
              <Radio className="w-3 h-3 text-emerald-600" />
              <span>FD001 Live</span>
            </div>

            <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200">
              <div className="w-8 h-8 rounded-full bg-slate-900 text-white font-bold text-xs flex items-center justify-center">
                AG
              </div>
              <div className="hidden lg:block text-left">
                <div className="text-xs font-semibold text-slate-900 leading-tight">
                  Ashwin Gaikwad
                </div>
                <div className="text-[10px] text-slate-400">Reliability Engineering</div>
              </div>
            </div>
          </div>
        </header>

        {/* Global Feedback Banner */}
        {feedbackMsg && (
          <div className="bg-sky-50 border-b border-sky-200 px-6 py-2.5 text-xs text-sky-900 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RefreshCw
                className={`w-3.5 h-3.5 ${
                  isDemoRunning ? "animate-spin text-sky-600" : "text-emerald-600"
                }`}
              />
              <span className="font-medium">{feedbackMsg}</span>
            </div>
            <button
              onClick={() => setFeedbackMsg(null)}
              className="text-slate-400 hover:text-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* MAIN BODY CONTAINER */}
        <main className="p-4 sm:p-8 max-w-7xl w-full mx-auto space-y-8 flex-1">
          
          {/* ========================================================= */}
          {/* TAB 1: FLEET OVERVIEW                                     */}
          {/* ========================================================= */}
          {activeTab === "overview" && (
            <div className="space-y-8">
              
              {/* Cockpit Overview Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
                <div>
                  <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
                    Fleet Reliability & RUL Cockpit
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-500 mt-1">
                    Real-time Remaining Useful Life estimation and degradation tracking for 100 NASA C-MAPSS turbofan units.
                  </p>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-auto">
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    Leak-Free Pipeline Active
                  </span>
                </div>
              </div>

              {/* Top KPI Metrics Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-xs">
                  <div className="flex items-center justify-between text-slate-500 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider">Active Fleet Units</span>
                    <Activity className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="text-3xl font-extrabold text-slate-900 font-mono">
                    {fleetSummary?.fleet_size ?? engines.length}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">100% operational monitoring</div>
                </div>

                <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-xs">
                  <div className="flex items-center justify-between text-slate-500 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider">Mean Fleet RUL</span>
                    <Clock className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="text-3xl font-extrabold text-slate-900 font-mono">
                    {fleetSummary?.mean_predicted_rul ? `${fleetSummary.mean_predicted_rul} cyc` : "108.4 cyc"}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">Projected engine lifespan</div>
                </div>

                <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-xs">
                  <div className="flex items-center justify-between text-slate-500 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider">Attention Required</span>
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                  </div>
                  <div className="text-3xl font-extrabold text-amber-600 font-mono">
                    {fleetSummary?.attention_required_count ?? 0}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">RUL &lt; 15 operating cycles</div>
                </div>

                <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-xs">
                  <div className="flex items-center justify-between text-slate-500 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider">Critical Grounding</span>
                    <ShieldAlert className="w-4 h-4 text-rose-500" />
                  </div>
                  <div className="text-3xl font-extrabold text-rose-600 font-mono">
                    {fleetSummary?.critical_engines?.length ?? 0}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">Immediate teardown review</div>
                </div>
              </div>

              {/* Fleet Maintenance Risk Distribution */}
              <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Fleet Maintenance Risk Distribution
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Classified according to calibrated operating cycle thresholds
                    </p>
                  </div>
                  <span className="text-xs font-mono font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
                    Total: {fleetSummary?.fleet_size || engines.length} units
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden flex">
                  {fleetSummary?.risk_distribution && (
                    <>
                      <div
                        style={{
                          width: `${((fleetSummary.risk_distribution.healthy || 0) / (fleetSummary.fleet_size || 1)) * 100}%`,
                        }}
                        className="bg-emerald-500 transition-all duration-500"
                        title={`Healthy (>30 cycles): ${fleetSummary.risk_distribution.healthy}`}
                      />
                      <div
                        style={{
                          width: `${((fleetSummary.risk_distribution.planning || 0) / (fleetSummary.fleet_size || 1)) * 100}%`,
                        }}
                        className="bg-sky-500 transition-all duration-500"
                        title={`Planning (15-30 cycles): ${fleetSummary.risk_distribution.planning}`}
                      />
                      <div
                        style={{
                          width: `${((fleetSummary.risk_distribution.attention || 0) / (fleetSummary.fleet_size || 1)) * 100}%`,
                        }}
                        className="bg-amber-500 transition-all duration-500"
                        title={`Attention (5-15 cycles): ${fleetSummary.risk_distribution.attention}`}
                      />
                      <div
                        style={{
                          width: `${((fleetSummary.risk_distribution.urgent || 0) / (fleetSummary.fleet_size || 1)) * 100}%`,
                        }}
                        className="bg-rose-500 transition-all duration-500"
                        title={`Urgent (<5 cycles): ${fleetSummary.risk_distribution.urgent}`}
                      />
                    </>
                  )}
                </div>

                {/* Badges */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 text-xs">
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                      <span className="text-slate-600 font-medium">Healthy (&gt;30 cyc)</span>
                    </div>
                    <span className="font-bold text-slate-900 font-mono">
                      {fleetSummary?.risk_distribution.healthy ?? 0}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-sky-500" />
                      <span className="text-slate-600 font-medium">Planning (15–30 cyc)</span>
                    </div>
                    <span className="font-bold text-slate-900 font-mono">
                      {fleetSummary?.risk_distribution.planning ?? 0}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                      <span className="text-slate-600 font-medium">Attention (5–15 cyc)</span>
                    </div>
                    <span className="font-bold text-slate-900 font-mono">
                      {fleetSummary?.risk_distribution.attention ?? 0}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                      <span className="text-slate-600 font-medium">Urgent (&lt;5 cyc)</span>
                    </div>
                    <span className="font-bold text-slate-900 font-mono">
                      {fleetSummary?.risk_distribution.urgent ?? 0}
                    </span>
                  </div>
                </div>
              </div>

              {/* Operational Action Pathways */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                <div
                  onClick={() => setActiveTab("engines")}
                  className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-xs hover:border-slate-300 hover:shadow-sm transition-all cursor-pointer flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700">
                      <Gauge className="w-5 h-5 text-slate-800" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">
                        Engine Diagnostic Center
                      </h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        Inspect individual turbofans, cycle wear progression, 90% confidence intervals, and NASA ground truth.
                      </p>
                    </div>
                  </div>
                  <div className="pt-4 flex items-center text-xs font-semibold text-slate-800 gap-1 hover:text-sky-600 transition-colors">
                    <span>Inspect engines</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>

                <div
                  onClick={() => setActiveTab("engines")}
                  className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-xs hover:border-slate-300 hover:shadow-sm transition-all cursor-pointer flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700">
                      <Sparkles className="w-5 h-5 text-slate-800" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">
                        Sensor Attribution & SHAP
                      </h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        Examine physical wear drivers across compressor outlet temperature (T30), static pressure, and bypass ratios.
                      </p>
                    </div>
                  </div>
                  <div className="pt-4 flex items-center text-xs font-semibold text-slate-800 gap-1 hover:text-sky-600 transition-colors">
                    <span>View attributions</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>

                <div
                  onClick={() => setActiveTab("models")}
                  className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-xs hover:border-slate-300 hover:shadow-sm transition-all cursor-pointer flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700">
                      <BarChart3 className="w-5 h-5 text-slate-800" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">
                        NASA Benchmark Evaluation
                      </h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        Compare Quantile Gradient Boosting against baseline models using NASA's asymmetric exponential loss function.
                      </p>
                    </div>
                  </div>
                  <div className="pt-4 flex items-center text-xs font-semibold text-slate-800 gap-1 hover:text-sky-600 transition-colors">
                    <span>Review benchmarks</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </div>

              {/* Two-Column Review Row: Critical Engines & Directives */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Critical Fleet Units */}
                <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-rose-600" />
                      <h4 className="text-sm font-bold text-slate-900">Critical Fleet Units</h4>
                    </div>
                    <span className="text-xs text-slate-400">Immediate Review Staging</span>
                  </div>

                  <div className="space-y-2">
                    {fleetSummary?.critical_engines && fleetSummary.critical_engines.length > 0 ? (
                      fleetSummary.critical_engines.map((c) => (
                        <div
                          key={c.engine_run_id}
                          className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/70 hover:border-slate-300 flex items-center justify-between transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono border ${
                                RISK_BADGES[c.risk_level as keyof typeof RISK_BADGES] ||
                                "bg-slate-100 text-slate-700"
                              }`}
                            >
                              {c.risk_level}
                            </span>
                            <div>
                              <div className="text-xs font-bold text-slate-900">
                                Engine Unit #{c.unit_number}
                              </div>
                              <div className="text-[11px] text-slate-500">
                                Operating Cycle: {c.cycle}
                              </div>
                            </div>
                          </div>

                          <div className="text-right">
                            <div className="text-sm font-extrabold text-rose-600 font-mono">
                              {c.predicted_rul} cyc
                            </div>
                            <div className="text-[10px] text-slate-400 font-mono">
                              90% CI: [{c.lower_bound} – {c.upper_bound}]
                            </div>
                          </div>

                          <button
                            onClick={() => {
                              setSelectedEngineId(c.engine_run_id);
                              setActiveTab("engines");
                            }}
                            className="p-1.5 rounded-md text-slate-400 hover:text-slate-900 hover:bg-slate-200 transition-colors ml-2 cursor-pointer"
                            title="Inspect engine details"
                          >
                            <ArrowRight className="w-4 h-4" />
                          </button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-xs text-slate-400">
                        No critical or urgent units currently flagged in active fleet.
                      </div>
                    )}
                  </div>
                </div>

                {/* Actionable Maintenance Directives */}
                <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <Wrench className="w-4 h-4 text-slate-700" />
                      <h4 className="text-sm font-bold text-slate-900">
                        Actionable Maintenance Directives
                      </h4>
                    </div>
                    <span className="text-[11px] text-slate-400">Research Benchmark Guidance</span>
                  </div>

                  <div className="space-y-3">
                    {fleetSummary?.latest_recommendations &&
                    fleetSummary.latest_recommendations.length > 0 ? (
                      fleetSummary.latest_recommendations.slice(0, 4).map((rec, i) => (
                        <div
                          key={i}
                          className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/70 space-y-1.5"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-bold text-slate-900">
                              Unit #{rec.unit_number}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] uppercase font-mono font-bold border ${
                                RISK_BADGES[rec.priority as keyof typeof RISK_BADGES] ||
                                "bg-slate-100 text-slate-700"
                              }`}
                            >
                              {rec.priority}
                            </span>
                          </div>
                          <p className="text-xs text-slate-600 leading-relaxed">
                            {rec.rationale}
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-xs text-slate-400">
                        Run the demo or model predictions to generate maintenance directives.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* TAB 2: ENGINE INSPECTOR                                   */}
          {/* ========================================================= */}
          {activeTab === "engines" && (
            <div className="space-y-6">
              
              {/* TWO-TIER HIGH-EFFICIENCY ENGINE SELECTOR TOOLBAR */}
              <div className="bg-white rounded-xl border border-slate-200/90 shadow-xs p-5 space-y-4">
                
                {/* TIER 1: Priority Action Units Quick-Filter Row */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3.5">
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-50 text-rose-700 text-xs font-semibold border border-rose-200">
                      <AlertOctagon className="w-3.5 h-3.5 text-rose-600" />
                      <span>Priority Action Units</span>
                    </div>
                    <span className="text-xs text-slate-400 hidden sm:inline">
                      Quick-switch units requiring priority inspection:
                    </span>
                  </div>

                  {/* Priority action quick pills */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    {priorityUnits.slice(0, 6).map((u) => {
                      const isSelected = selectedEngineId === u.id;
                      const isUrgent = u.risk_level === "urgent";
                      const isAttention = u.risk_level === "attention";
                      return (
                        <button
                          key={u.id}
                          onClick={() => setSelectedEngineId(u.id)}
                          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono transition-all cursor-pointer ${
                            isSelected
                              ? "bg-slate-900 text-white font-bold shadow-xs ring-2 ring-slate-900 ring-offset-1"
                              : isUrgent
                              ? "bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200"
                              : isAttention
                              ? "bg-amber-50 text-amber-800 hover:bg-amber-100 border border-amber-200"
                              : "bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isSelected
                                ? "bg-sky-400"
                                : isUrgent
                                ? "bg-rose-500"
                                : isAttention
                                ? "bg-amber-500"
                                : "bg-slate-400"
                            }`}
                          />
                          <span>Unit #{u.unit_number}</span>
                          <span className={`text-[10px] ${isSelected ? "text-slate-300" : "opacity-75"}`}>
                            ({u.predicted_rul !== null ? `${u.predicted_rul}c` : `${u.max_cycle}c`})
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* TIER 2: Searchable Combobox Trigger & Stepper Controls */}
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-2 relative">
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wider pr-1">
                      Active Unit:
                    </span>

                    {/* Previous Unit Stepper Button */}
                    <button
                      onClick={handlePrevUnit}
                      title="Previous engine unit"
                      className="p-2 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>

                    {/* Custom Popover Combobox Anchor */}
                    <div className="relative" ref={pickerRef}>
                      <button
                        type="button"
                        onClick={() => setIsPickerOpen(!isPickerOpen)}
                        className="flex items-center justify-between gap-3 px-3.5 py-2 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-900 text-xs font-mono transition-all cursor-pointer min-w-[270px] sm:min-w-[320px]"
                      >
                        <div className="flex items-center gap-2">
                          <Cpu className="w-3.5 h-3.5 text-slate-600" />
                          <span className="font-bold text-slate-900 text-sm">
                            {currentEngine ? `Unit #${currentEngine.unit_number}` : "Select Unit"}
                          </span>
                          {currentEngine && (
                            <>
                              <span className="text-slate-400 uppercase text-[10px] font-semibold">
                                ({currentEngine.file_role})
                              </span>
                              <span className="text-slate-500 text-[11px]">
                                • {currentEngine.max_cycle} cyc
                              </span>
                            </>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          {currentEngine?.risk_level && (
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border ${
                                RISK_BADGES[currentEngine.risk_level]
                              }`}
                            >
                              {currentEngine.risk_level}
                            </span>
                          )}
                          <ChevronDown
                            className={`w-3.5 h-3.5 text-slate-500 transition-transform ${
                              isPickerOpen ? "rotate-180" : ""
                            }`}
                          />
                        </div>
                      </button>

                      {/* Searchable Engine Picker Dropdown Popover */}
                      {isPickerOpen && (
                        <div className="absolute left-0 top-full mt-2 w-80 sm:w-96 bg-white rounded-xl border border-slate-200 shadow-xl z-50 p-3 space-y-3 animate-in fade-in zoom-in-95 duration-100">
                          {/* Search Input inside popover */}
                          <div className="relative">
                            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                            <input
                              type="text"
                              value={pickerSearch}
                              onChange={(e) => setPickerSearch(e.target.value)}
                              placeholder="Search unit #, role, or risk..."
                              autoFocus
                              className="w-full pl-8 pr-7 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-slate-400 font-mono text-slate-900 placeholder:text-slate-400"
                            />
                            {pickerSearch && (
                              <button
                                onClick={() => setPickerSearch("")}
                                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            )}
                          </div>

                          {/* Quick Filter Category Chips */}
                          <div className="flex flex-wrap gap-1 text-[11px]">
                            {[
                              { id: "all", label: "All Units" },
                              { id: "urgent", label: "Urgent" },
                              { id: "attention", label: "Attention" },
                              { id: "planning", label: "Planning" },
                              { id: "healthy", label: "Healthy" },
                              { id: "test", label: "Test Split" },
                            ].map((chip) => (
                              <button
                                key={chip.id}
                                onClick={() => setPickerFilterRisk(chip.id)}
                                className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors cursor-pointer ${
                                  pickerFilterRisk === chip.id
                                    ? "bg-slate-900 text-white font-bold"
                                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                                }`}
                              >
                                {chip.label}
                              </button>
                            ))}
                          </div>

                          {/* Scrollable Unit Directory */}
                          <div className="max-h-60 overflow-y-auto divide-y divide-slate-100 border border-slate-100 rounded-lg">
                            {pickerFilteredUnits.length > 0 ? (
                              pickerFilteredUnits.map((e) => {
                                const isSelected = selectedEngineId === e.id;
                                return (
                                  <button
                                    key={e.id}
                                    onClick={() => {
                                      setSelectedEngineId(e.id);
                                      setIsPickerOpen(false);
                                    }}
                                    className={`w-full flex items-center justify-between px-3 py-2 text-xs font-mono text-left transition-colors cursor-pointer ${
                                      isSelected
                                        ? "bg-sky-50 text-sky-950 font-bold"
                                        : "hover:bg-slate-50 text-slate-800"
                                    }`}
                                  >
                                    <div className="flex items-center gap-2">
                                      {isSelected && <Check className="w-3.5 h-3.5 text-sky-600 shrink-0" />}
                                      <span className={isSelected ? "font-bold text-slate-900" : ""}>
                                        Unit #{e.unit_number}
                                      </span>
                                      <span className="text-[10px] text-slate-400 uppercase">
                                        ({e.file_role})
                                      </span>
                                    </div>

                                    <div className="flex items-center gap-2">
                                      <span className="text-[11px] text-slate-500">
                                        {e.predicted_rul !== null ? `${e.predicted_rul} cyc` : `${e.max_cycle} cyc`}
                                      </span>
                                      {e.risk_level && (
                                        <span
                                          className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-bold border ${
                                            RISK_BADGES[e.risk_level]
                                          }`}
                                        >
                                          {e.risk_level}
                                        </span>
                                      )}
                                    </div>
                                  </button>
                                );
                              })
                            ) : (
                              <div className="p-4 text-center text-xs text-slate-400">
                                No matching engine units found.
                              </div>
                            )}
                          </div>

                          {/* Popover Footer Summary */}
                          <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-100">
                            <span>Showing {pickerFilteredUnits.length} of {engines.length} units</span>
                            <button
                              onClick={() => setIsPickerOpen(false)}
                              className="text-xs text-slate-600 hover:text-slate-900 font-semibold cursor-pointer"
                            >
                              Close
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Next Unit Stepper Button */}
                    <button
                      onClick={handleNextUnit}
                      title="Next engine unit"
                      className="p-2 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Current Engine Status Pills */}
                  {engineDetail && (
                    <div className="flex items-center gap-2 text-xs">
                      <div className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 font-mono font-medium">
                        Max Cycles: <span className="font-bold text-slate-900">{engineDetail.max_cycle}</span>
                      </div>
                      {engineDetail.prediction && (
                        <div
                          className={`px-3 py-1.5 rounded-lg border font-mono font-bold uppercase ${
                            RISK_BADGES[engineDetail.prediction.risk_level]
                          }`}
                        >
                          Status: {engineDetail.prediction.risk_level}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {engineDetail && (
                <>
                  {/* Gauge Card & Directive */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs flex flex-col justify-between">
                      <div className="flex items-center justify-between text-slate-500 mb-2">
                        <span className="text-xs uppercase tracking-wider font-semibold">
                          Remaining Useful Life
                        </span>
                        <Gauge className="w-4 h-4 text-slate-400" />
                      </div>

                      <div className="text-center my-4">
                        <div className="text-5xl font-black font-mono text-slate-900 tracking-tight">
                          {engineDetail.prediction?.predicted_rul ?? "—"}
                          <span className="text-lg text-slate-400 ml-2 font-normal">cycles</span>
                        </div>

                        {engineDetail.prediction && (
                          <div className="text-xs text-slate-500 mt-2 font-medium">
                            90% Prediction Interval:{" "}
                            <span className="font-mono text-slate-900 font-bold">
                              [{engineDetail.prediction.lower_bound} – {engineDetail.prediction.upper_bound}]
                            </span>
                          </div>
                        )}

                        {engineDetail.ground_truth_rul !== null && (
                          <div className="mt-3 inline-block px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-mono">
                            NASA Ground Truth RUL:{" "}
                            <span className="font-bold text-emerald-700">
                              {engineDetail.ground_truth_rul} cycles
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="border-t border-slate-100 pt-3 text-[11px] text-slate-400 text-center">
                        Estimated using piece-wise linear wear degradation model.
                      </div>
                    </div>

                    <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs flex flex-col justify-between lg:col-span-2">
                      <div>
                        <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
                          <div className="flex items-center gap-2">
                            <Wrench className="w-4 h-4 text-slate-700" />
                            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                              Maintenance Guidance Directive
                            </span>
                          </div>
                          {engineDetail.recommendation && (
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono border ${
                                RISK_BADGES[engineDetail.recommendation.priority]
                              }`}
                            >
                              {engineDetail.recommendation.priority}
                            </span>
                          )}
                        </div>

                        <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 text-xs sm:text-sm leading-relaxed text-slate-800">
                          {engineDetail.recommendation?.rationale ||
                            "No specific directive generated for this unit yet."}
                        </div>
                      </div>

                      <div className="text-[11px] text-slate-400 mt-4 flex items-center gap-1.5">
                        <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
                        <span>Simulated C-MAPSS benchmark analysis. Not operational flight dispatch authorization.</span>
                      </div>
                    </div>
                  </div>

                  {/* SHAP Feature Attribution Waterfall */}
                  {engineDetail.explanation && (
                    <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs space-y-4">
                      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                        <div>
                          <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-sky-600" />
                            SHAP Degradation Attributions
                          </h4>
                          <p className="text-xs text-slate-500 mt-0.5">
                            {engineDetail.explanation.summary}
                          </p>
                        </div>
                        <span className="text-[11px] font-mono text-slate-400">
                          Method: {engineDetail.explanation.method}
                        </span>
                      </div>

                      <div className="space-y-2 pt-1">
                        {engineDetail.explanation.top_contributors.map((c, idx) => {
                          const isReduction = c.direction === "decreases_rul";
                          return (
                            <div
                              key={idx}
                              className="flex items-center justify-between text-xs p-3 rounded-lg bg-slate-50 border border-slate-100"
                            >
                              <div className="flex items-center gap-2.5">
                                {isReduction ? (
                                  <TrendingDown className="w-4 h-4 text-rose-600" />
                                ) : (
                                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                                )}
                                <span className="font-semibold text-slate-800">
                                  {c.description}
                                </span>
                                <span className="text-slate-400 text-[11px] font-mono">
                                  ({c.feature})
                                </span>
                              </div>

                              <div className="flex items-center gap-3">
                                <span
                                  className={`font-mono font-bold ${
                                    isReduction ? "text-rose-600" : "text-emerald-600"
                                  }`}
                                >
                                  {c.attribution > 0 ? `+${c.attribution}` : c.attribution}
                                </span>
                                <span
                                  className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold uppercase ${
                                    isReduction
                                      ? "bg-rose-50 text-rose-700"
                                      : "bg-emerald-50 text-emerald-700"
                                  }`}
                                >
                                  {isReduction ? "Wear Driver" : "Life Extender"}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Multi-Sensor Telemetry Time-Series Chart */}
                  <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-3">
                      <div>
                        <h4 className="text-sm font-bold text-slate-900">
                          Cycle-by-Cycle Telemetry Series
                        </h4>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Raw operational sensor trends along engine operational cycles
                        </p>
                      </div>

                      {/* Sensor Selector Pills */}
                      <div className="flex flex-wrap gap-1 text-xs">
                        {[
                          { id: "sensor_2", label: "T24 (LPC Temp)" },
                          { id: "sensor_3", label: "T30 (HPC Temp)" },
                          { id: "sensor_4", label: "T50 (LPT Temp)" },
                          { id: "sensor_7", label: "P30 (HPC Press)" },
                          { id: "sensor_9", label: "Nc (Core Speed)" },
                          { id: "sensor_11", label: "Ps30 (Static Press)" },
                          { id: "sensor_15", label: "BPR (Bypass Ratio)" },
                          { id: "sensor_21", label: "W32 (Coolant Bleed)" },
                        ].map((s) => (
                          <button
                            key={s.id}
                            onClick={() => setSelectedSensor(s.id)}
                            className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors cursor-pointer ${
                              selectedSensor === s.id
                                ? "bg-slate-900 text-white font-bold"
                                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                            }`}
                          >
                            {s.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="h-72 w-full pt-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis
                            dataKey="cycle"
                            stroke="#94a3b8"
                            fontSize={11}
                            tickLine={false}
                            label={{
                              value: "Operational Cycles",
                              position: "insideBottom",
                              offset: -5,
                              fill: "#64748b",
                              fontSize: 11,
                            }}
                          />
                          <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} domain={["auto", "auto"]} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: "#ffffff",
                              borderColor: "#e2e8f0",
                              borderRadius: "8px",
                              fontSize: "12px",
                              boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
                            }}
                          />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#0284c7"
                            strokeWidth={2}
                            dot={false}
                            activeDot={{ r: 4, fill: "#0284c7" }}
                            name={selectedSensor}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ========================================================= */}
          {/* TAB 3: DATASETS EXPLORER                                  */}
          {/* ========================================================= */}
          {activeTab === "datasets" && (
            <div className="space-y-6">
              <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Dataset Lineage & Validation
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    NASA C-MAPSS FD001 raw whitespace files and preprocessed feature matrices
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={runOneClickDemo}
                    disabled={isDemoRunning}
                    className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isDemoRunning ? "animate-spin" : ""}`} />
                    <span>Re-Ingest Samples</span>
                  </button>
                </div>
              </div>

              {/* Datasets Table */}
              <div className="bg-white rounded-xl border border-slate-200/90 shadow-xs overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                    Available Datasets
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    {datasets.length} registered
                  </span>
                </div>

                <div className="divide-y divide-slate-100">
                  {datasets.map((ds) => (
                    <div
                      key={ds.id}
                      className="p-6 flex flex-wrap items-center justify-between gap-4 hover:bg-slate-50/60 transition-colors"
                    >
                      <div>
                        <div className="flex items-center gap-2.5">
                          <span className="font-bold text-sm text-slate-900">{ds.dataset_code}</span>
                          <span className="text-xs text-slate-500">— {ds.source_name}</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {ds.status}
                          </span>
                        </div>
                        <div className="text-xs text-slate-500 mt-2 flex flex-wrap items-center gap-4">
                          <span>
                            Train Engines: <strong className="text-slate-800">{ds.train_count}</strong>
                          </span>
                          <span>
                            Test Engines: <strong className="text-slate-800">{ds.test_count}</strong>
                          </span>
                          <span>
                            Ground Truth RUL:{" "}
                            <strong className="text-slate-800">{ds.has_test_rul ? "Yes" : "No"}</strong>
                          </span>
                        </div>
                      </div>

                      <button
                        onClick={() => handleDatasetChange(ds.id)}
                        className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                          selectedDatasetId === ds.id
                            ? "bg-slate-900 text-white"
                            : "bg-slate-100 hover:bg-slate-200 text-slate-700"
                        }`}
                      >
                        {selectedDatasetId === ds.id ? "Active Dataset" : "Switch Dataset"}
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Filtered Engine Directory */}
              <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-3">
                  <h4 className="text-sm font-bold text-slate-900">Engine Runs Directory</h4>
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                      <input
                        type="text"
                        placeholder="Filter Unit ID..."
                        value={searchUnit}
                        onChange={(e) => setSearchUnit(e.target.value)}
                        className="bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-slate-400 w-36 font-mono"
                      />
                    </div>

                    <select
                      value={filterRisk}
                      onChange={(e) => setFilterRisk(e.target.value)}
                      className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-slate-400 font-mono"
                    >
                      <option value="all">All Risk Levels</option>
                      <option value="healthy">Healthy</option>
                      <option value="planning">Planning</option>
                      <option value="attention">Attention</option>
                      <option value="urgent">Urgent</option>
                    </select>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-100 text-slate-500 uppercase font-mono">
                      <tr>
                        <th className="py-2.5 px-3">Unit</th>
                        <th className="py-2.5 px-3">Role</th>
                        <th className="py-2.5 px-3">Operational Cycles</th>
                        <th className="py-2.5 px-3">Estimated RUL</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      {filteredEngines.map((e) => (
                        <tr key={e.id} className="hover:bg-slate-50/60">
                          <td className="py-2.5 px-3 font-bold text-slate-900">Unit #{e.unit_number}</td>
                          <td className="py-2.5 px-3 uppercase text-slate-500">{e.file_role}</td>
                          <td className="py-2.5 px-3 text-slate-700">{e.max_cycle} cycles</td>
                          <td className="py-2.5 px-3 font-bold text-slate-900">
                            {e.predicted_rul !== null ? `${e.predicted_rul} cyc` : "—"}
                          </td>
                          <td className="py-2.5 px-3">
                            {e.risk_level ? (
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold border ${
                                  RISK_BADGES[e.risk_level as keyof typeof RISK_BADGES]
                                }`}
                              >
                                {e.risk_level}
                              </span>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              onClick={() => {
                                setSelectedEngineId(e.id);
                                setActiveTab("engines");
                              }}
                              className="text-slate-900 hover:text-sky-600 font-semibold cursor-pointer"
                            >
                              Inspect &rarr;
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* TAB 4: MODEL REGISTRY & BENCHMARK EVALUATION              */}
          {/* ========================================================= */}
          {activeTab === "models" && (
            <div className="space-y-6">
              {/* Header & NASA Scoring Card */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs lg:col-span-2 space-y-3">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-slate-700" />
                    Model Registry & Benchmark Evaluation
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Evaluated models adhere to NASA C-MAPSS benchmark protocols. Features and scalers
                    are fitted strictly on training engine units, eliminating sequence leakage. Official
                    evaluation computes asymmetric penalties where overestimating RUL carries higher cost
                    than conservative predictions.
                  </p>

                  <div className="flex flex-wrap gap-3 pt-2 text-xs font-mono">
                    <div className="px-3 py-1.5 rounded-md bg-slate-100 text-slate-700">
                      Degradation Target Cap: <strong className="text-slate-900">125 cycles</strong>
                    </div>
                    <div className="px-3 py-1.5 rounded-md bg-slate-100 text-slate-700">
                      Cross-Validation: <strong className="text-slate-900">Group by Engine Unit</strong>
                    </div>
                  </div>
                </div>

                {/* NASA Formula Card */}
                <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs flex flex-col justify-between">
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                      Official NASA Score
                    </h4>
                    <div className="text-[11px] font-mono bg-slate-50 p-3 rounded-lg border border-slate-200 text-slate-700 space-y-1">
                      <div>d = Predicted - Actual (cycles)</div>
                      <div className="text-emerald-700 font-semibold">d &lt; 0: s = exp(-d/13) - 1</div>
                      <div className="text-rose-700 font-semibold">d &ge; 0: s = exp(d/10) - 1</div>
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-2">
                    Penalizes dangerous late failure predictions exponentially more than early predictions.
                  </div>
                </div>
              </div>

              {/* Models Table */}
              <div className="bg-white rounded-xl border border-slate-200/90 shadow-xs overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                    Trained Model Versions
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    {models.length} registered
                  </span>
                </div>

                <div className="divide-y divide-slate-100">
                  {models.map((m) => (
                    <div
                      key={m.id}
                      className="p-6 flex flex-wrap items-center justify-between gap-4 hover:bg-slate-50/60 transition-colors"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-slate-900 font-mono">
                            {m.version}
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {m.status}
                          </span>
                        </div>
                        <div className="text-xs text-slate-500 mt-2 flex flex-wrap gap-4 font-mono">
                          <span>
                            RMSE: <strong className="text-slate-800">{m.metrics?.rmse ?? "—"} cyc</strong>
                          </span>
                          <span>
                            MAE: <strong className="text-slate-800">{m.metrics?.mae ?? "—"} cyc</strong>
                          </span>
                          <span>
                            R²: <strong className="text-slate-800">{m.metrics?.r2 ?? "—"}</strong>
                          </span>
                          <span>
                            NASA Score:{" "}
                            <strong className="text-slate-900">{m.metrics?.nasa_score ?? "—"}</strong>
                          </span>
                        </div>
                      </div>

                      <button
                        onClick={() => {
                          if (selectedDatasetId) {
                            api.runPredictions(m.id, selectedDatasetId, "test").then(() => refreshAll());
                          }
                        }}
                        className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium transition-colors cursor-pointer"
                      >
                        Run Test Batch Predictions
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Actual vs Predicted RUL Scatter Plot */}
              {evaluationScatterData.length > 0 && (
                <div className="bg-white p-6 rounded-xl border border-slate-200/90 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">
                        Test Predictions vs NASA Ground Truth RUL
                      </h4>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Evaluation on test units at their final operational cycle
                      </p>
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      {evaluationScatterData.length} units plotted
                    </span>
                  </div>

                  <div className="h-72 w-full pt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis
                          type="number"
                          dataKey="actual"
                          name="Actual RUL"
                          stroke="#94a3b8"
                          fontSize={11}
                          tickLine={false}
                          label={{
                            value: "Actual RUL (cycles)",
                            position: "insideBottom",
                            offset: -5,
                            fill: "#64748b",
                            fontSize: 11,
                          }}
                        />
                        <YAxis
                          type="number"
                          dataKey="predicted"
                          name="Predicted RUL"
                          stroke="#94a3b8"
                          fontSize={11}
                          tickLine={false}
                          label={{
                            value: "Predicted RUL (cycles)",
                            angle: -90,
                            position: "insideLeft",
                            fill: "#64748b",
                            fontSize: 11,
                          }}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#ffffff",
                            borderColor: "#e2e8f0",
                            borderRadius: "8px",
                            fontSize: "12px",
                            boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
                          }}
                        />
                        <ReferenceLine x={0} y={0} stroke="#cbd5e1" strokeDasharray="3 3" />
                        <Scatter name="Test Units" data={evaluationScatterData} fill="#0284c7" />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>

        {/* Footer */}
        <footer className="border-t border-slate-200 py-4 px-8 text-center text-xs text-slate-400 bg-white">
          TelemetryX — Predictive Maintenance & Remaining Useful Life (RUL) Cockpit. NASA C-MAPSS Turbofan Benchmark.
        </footer>
      </div>
    </div>
  );
}
