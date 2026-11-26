import { useEffect, useId, useMemo, useRef, useState } from "react";
import { normalize } from "../utils/places";

const MAX_RESULTS = 50;

// Camp text cu lista de sugestii; valoarea poate fi doar una dintre optiuni
export default function Combobox({id,options,value,onChange,placeholder,disabled,required}) {
    const [query,setQuery] = useState("");
    const [open,setOpen] = useState(false);
    const [active,setActive] = useState(0);
    const listRef = useRef(null);
    const listId = useId();

    const indexed = useMemo(()=>options.map((option)=>[option,normalize(option)]),[options]);
    const results = useMemo(()=>{
        const needle = normalize(query);
        if(!needle) return options;
        const starts = [], contains = [];
        for(const [option,key] of indexed){
            if(key.startsWith(needle)) starts.push(option);
            else if(key.includes(needle)) contains.push(option);
        }
        return starts.concat(contains);
    },[indexed,options,query]);
    const shown = results.slice(0,MAX_RESULTS);

    useEffect(()=>{
        listRef.current?.children[active]?.scrollIntoView({block:"nearest"});
    },[active,open]);

    function openList(){
        setQuery("");
        setActive(0);
        setOpen(true);
    }

    function pick(option){
        onChange(option);
        setOpen(false);
    }

    // La iesirea din camp: textul scris exact se accepta, altfel revine la valoarea aleasa
    function commit(){
        if(!open) return;
        const exact = indexed.find(([,key])=>key===normalize(query));
        if(exact) onChange(exact[0]);
        setOpen(false);
    }

    function handleKeyDown(event){
        if(event.key==="ArrowDown" || event.key==="ArrowUp"){
            event.preventDefault();
            if(!open){ openList(); return; }
            const step = event.key==="ArrowDown" ? 1 : -1;
            setActive((current)=>Math.min(Math.max(current+step,0),shown.length-1));
        }else if(event.key==="Enter" && open){
            event.preventDefault();
            if(shown[active]) pick(shown[active]);
        }else if(event.key==="Escape" && open){
            event.preventDefault();
            setOpen(false);
        }
    }

    return <div className="relative">
        <input id={id} role="combobox" autoComplete="off" aria-autocomplete="list" aria-expanded={open} aria-controls={listId}
            aria-activedescendant={open && shown[active] ? `${listId}-${active}` : undefined}
            value={open ? query : value} placeholder={placeholder} disabled={disabled} required={required}
            onFocus={openList} onClick={()=>{ if(!open) openList(); }}
            onChange={(e)=>{ setQuery(e.target.value); setActive(0); setOpen(true); }}
            onBlur={commit} onKeyDown={handleKeyDown}/>
        {/* preventDefault pe click: lista e in <label>, iar click-ul ar redeschide campul dupa alegere */}
        {open && <ul id={listId} ref={listRef} role="listbox" onMouseDown={(e)=>e.preventDefault()} onClick={(e)=>e.preventDefault()}
            className="absolute inset-x-0 top-full z-[1100] mt-1 max-h-64 overflow-y-auto rounded-lg border border-line bg-white py-1 text-sm font-normal shadow-[var(--shadow-soft)]">
            {results.length===0 && <li className="px-3 py-2 text-muted">Niciun rezultat</li>}
            {shown.map((option,index)=><li key={option} id={`${listId}-${index}`} role="option" aria-selected={option===value}
                onMouseEnter={()=>setActive(index)} onClick={()=>pick(option)}
                className={`cursor-pointer px-3 py-2 ${index===active ? "bg-aqua-soft" : ""} ${option===value ? "font-semibold" : ""}`}>{option}</li>)}
            {results.length>MAX_RESULTS && <li className="px-3 py-2 text-xs text-muted">
                Încă {results.length-MAX_RESULTS} rezultate. Scrie mai mult pentru a restrânge lista.</li>}
        </ul>}
    </div>;
}
