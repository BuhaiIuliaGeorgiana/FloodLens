export const emptyProfile = {first_name:"",last_name:"",job_title:"",department:""};
export default function MemberProfileFields({value,onChange,disabled=false,legend="Profil profesional"}) {
    const fields=[["last_name","Nume",100],["first_name","Prenume",100],["job_title","Funcție",120],["department","Departament",120]];
    return <fieldset disabled={disabled}><legend>{legend}</legend>{fields.map(([key,label,max])=>
        <label key={key}>{label}<input name={key} required maxLength={max} value={value[key] ?? ""}
            onChange={e=>onChange({...value,[key]:e.target.value})}/></label>)}</fieldset>;
}
