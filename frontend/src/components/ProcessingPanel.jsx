import { useState, useEffect, useRef } from "react";

import { useAuth } from "../hooks/useAuth";
import {
    ACTIVE_STATUSES,
    isPipelineConfigured,
    getLatestRun,
    startProcessing,
} from "../services/pipelineService";

// How often to check the status while a run is in progress
const POLL_INTERVAL_MS = 5000;

const STATUS_LABELS = {
    queued: "Queued",
    processing: "Processing",
    ready: "Ready",
    partial: "Partially ready",
    waiting_for_data: "Waiting for new images",
    failed: "Failed",
};

const SOURCE_LABELS = {
    sentinel1: "Sentinel-1",
    sentinel2: "Sentinel-2",
    osm: "OpenStreetMap exposure",
};

function formatDateTime(value){
    return new Date(value).toLocaleString("ro-RO", {
        timeZone: "Europe/Bucharest"
    });
}

// "Proceseaza / Actualizeaza" button and the status of the latest run.
// Calls onRunFinished when a run ends, so the page can reload the layers.
function ProcessingPanel({ eventId, onRunFinished }){
    const {user} = useAuth();
    const [run,setRun] = useState(null);
    const [loading,setLoading] = useState(true);
    const [starting,setStarting] = useState(false);
    const [error,setError] = useState("");

    const onRunFinishedRef = useRef(onRunFinished);
    const previousStatus = useRef(null);

    useEffect(() => {
        onRunFinishedRef.current = onRunFinished;
    }, [onRunFinished]);

    const isActive = run && ACTIVE_STATUSES.includes(run.status);

    // Load the latest run, then keep checking while it is active
    useEffect(() => {
        let ignore = false;
        let timer = null;

        async function loadRun(){
            try{
                const data = await getLatestRun(eventId);

                if(ignore){
                    return;
                }

                setRun(data);
                setError("");

                const wasActive = ACTIVE_STATUSES.includes(previousStatus.current);
                const nowActive = data && ACTIVE_STATUSES.includes(data.status);

                if(wasActive && !nowActive){
                    onRunFinishedRef.current?.();
                }

                previousStatus.current = data?.status ?? null;

                if(nowActive){
                    timer = setTimeout(loadRun, POLL_INTERVAL_MS);
                }
            }catch(err){
                if(!ignore){
                    setError(err.message);
                }
            }finally{
                if(!ignore){
                    setLoading(false);
                }
            }
        }

        loadRun();

        return () => {
            ignore = true;
            clearTimeout(timer);
        };

    // isActive restarts polling after a new run is started
    }, [eventId, isActive]);

    async function handleProcess(){
        setError("");
        setStarting(true);

        try{
            const runId = await startProcessing(eventId);

            // Show the new run as queued until the first status check.
            // The service creates the pipeline_runs row before replying.
            previousStatus.current = "queued";
            setRun({
                id: runId,
                status: "queued",
                source_status: {},
                message: null,
                created_at: new Date().toISOString(),
            });
        }catch(err){
            setError(err.message);
        }finally{
            setStarting(false);
        }
    }

    const sources = Object.entries(run?.source_status ?? {});

    return(
        <section>
            <h2>Processing</h2>

            {loading && <p>Loading status...</p>}

            {!loading && !run && (
                <p>This event has not been processed yet.</p>
            )}

            {run && (
                <div>
                    <p>
                        Status: <strong>{STATUS_LABELS[run.status] ?? run.status}</strong>
                        {" "}(started {formatDateTime(run.created_at)})
                    </p>

                    {sources.length > 0 && (
                        <ul>
                            {sources.map(([source, status]) => (
                                <li key={source}>
                                    {SOURCE_LABELS[source] ?? source}:
                                    {" "}{STATUS_LABELS[status] ?? status}
                                </li>
                            ))}
                        </ul>
                    )}

                    {run.message && <p>{run.message}</p>}
                </div>
            )}

            {user && (
                <button
                    onClick={handleProcess}
                    disabled={!isPipelineConfigured || starting || isActive}
                >
                    {starting
                        ? "Starting..."
                        : run ? "Actualizeaza" : "Proceseaza"}
                </button>
            )}

            {user && !isPipelineConfigured && (
                <p>Processing service not configured yet.</p>
            )}

            {error && <p role="alert">{error}</p>}
        </section>
    );
}

export default ProcessingPanel;
