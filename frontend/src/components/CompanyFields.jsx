export const emptyCompany = {name:"",tax_id:"",country:"România",address:"",contact_email:"",phone:"",website:""};
export default function CompanyFields({value,onChange,disabled=false}) {
    const fields = [
        ["name","Denumire legală","text",200,true], ["tax_id","CUI / identificator fiscal","text",100,true],
        ["country","Țară","text",100,true], ["address","Adresă sediu","text",500,true],
        ["contact_email","Email de contact","email",254,true], ["phone","Telefon (opțional)","tel",50,false],
        ["website","Website (opțional)","url",500,false]
    ];
    return <fieldset disabled={disabled}><legend>Datele firmei</legend>{fields.map(([key,label,type,max,required])=>
        <label key={key}>{label}<input name={key} type={type} value={value[key] ?? ""} maxLength={max} required={required}
            onChange={e=>onChange({...value,[key]:e.target.value})}/></label>)}</fieldset>;
}
