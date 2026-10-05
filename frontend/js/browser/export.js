import { designFor, fontFiles } from "../core/document-designs.js";
export function parseLines(content) {
  return content.split(/\r?\n/).map(raw => {
    const text = raw.trim().replace(/\*\*/g, '').replace(/`/g, '');
    const match = /^(#{1,3})\s+(.+)$/.exec(text);
    if (match) return { type:`h${match[1].length}`, text:match[2] };
    if (/^[-*]\s/.test(text)) return {type:'bullet',text:text.slice(2)};
    if (text.startsWith('> ')) return {type:'note',text:text.slice(2)};
    return {type:text ? 'text':'blank',text};
  });
}
async function photoBytes(photo) {
  if (!photo) return null;
  if (!/^data:image\/(png|jpeg|webp);base64,/.test(photo)) throw new Error('Ungültiges Foto / invalid photo.');
  // Normalize WebP and scale all formats so Word and PDF receive the same supported PNG.
  if (typeof document === 'undefined') return {bytes:Uint8Array.from(atob(photo.split(',')[1]),c=>c.charCodeAt(0)),type:photo.startsWith('data:image/png')?'png':'jpg',width:80,height:100};
  const image = new Image();
  image.src = photo;
  await image.decode();
  const scale = Math.min(1, 800/Math.max(image.width,image.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(image.width*scale); canvas.height = Math.round(image.height*scale);
  canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
  return {bytes:Uint8Array.from(atob(canvas.toDataURL('image/png').split(',')[1]),c=>c.charCodeAt(0)),type:'png',width:canvas.width,height:canvas.height};
}
export async function createPdf(body, fontBytes) {
  const { PDFDocument, rgb } = await import('pdf-lib');
  const { default: fontkit } = await import('@pdf-lib/fontkit');
  const theme = designFor(body.design);
  const pdf = await PDFDocument.create();
  pdf.registerFontkit(fontkit);
  const files = fontFiles(theme);
  if (!fontBytes) {
    const load = async filename => {
      const response = await fetch(new URL('../../static/fonts/' + filename, import.meta.url));
      if (!response.ok) throw new Error('PDF-Schrift konnte nicht geladen werden / unable to load PDF font.');
      return response.arrayBuffer();
    };
    const [regular, bold] = await Promise.all([load(files.regular), load(files.bold)]);
    fontBytes = {regular,bold};
  }
  const font = await pdf.embedFont(fontBytes.regular || fontBytes, { subset:true });
  const boldFont = fontBytes.bold ? await pdf.embedFont(fontBytes.bold, {subset:true}) : font;
  const hex = value => rgb(...value.match(/../g).map(x=>parseInt(x,16)/255));
  const color = hex(theme.accent), ink = hex(theme.ink), muted = hex(theme.muted), rule = hex(theme.rule), surface = hex(theme.surface);
  const supported = new Set(font.getCharacterSet());
  const clean = text => Array.from(text).filter(c=>supported.has(c.codePointAt(0))).join('');
  const width = 595.28, height = 841.89, margin = 48;
  let page, y;
  const addPage = () => {
    page = pdf.addPage([width,height]); y = height-margin;
    if (theme.rail) page.drawRectangle({x:0,y:0,width:13,height,color});
    if (theme.topbar) page.drawRectangle({x:margin,y:height-25,width:width-margin*2,height:3,color});
  };
  addPage();
  const photo = await photoBytes(body.photo);
  let photoBottom = height;
  if (photo) {
    const image = photo.type === 'png' ? await pdf.embedPng(photo.bytes) : await pdf.embedJpg(photo.bytes);
    const size = image.scaleToFit(76,92);
    page.drawImage(image,{x:theme.centered?(width-size.width)/2:width-margin-size.width,y:y-size.height,width:size.width,height:size.height});
    if (theme.centered) y-=size.height+14;
    else photoBottom = y-size.height-12;
  }
  let identity = false;
  const resume = !body.document || body.document === 'cv';
  for (const line of parseLines(body.content)) {
    if (line.type === 'blank') { y-=6; continue; }
    if (line.type === 'h1') identity = true;
    if (['h2','h3','bullet'].includes(line.type)) identity = false;
    const heading = line.type.startsWith('h');
    const face = heading ? boldFont : font;
    const size = line.type === 'h1' ? theme.nameSize : line.type === 'h2' ? theme.sectionSize : line.type === 'h3' ? 10.5 : line.type === 'note' ? 8.5 : 10;
    if (heading) y-=line.type === 'h1' ? 0:line.type === 'h2' ? 14:8;
    if (y < margin+size*3) addPage();
    const text = clean((line.type === 'bullet' ? '• ': '')+(line.type === 'h2' && theme.uppercase ? line.text.toUpperCase() : line.text));
    const available = width-margin*2-(y>photoBottom && pdf.getPageCount()===1 ? 96:0);
    // Wrap even long URLs or unbroken words; no text is silently truncated.
    const rows=[]; let current='';
    for (const word of text.split(/\s+/)) {
      const trial = current ? `${current} ${word}` : word;
      if (face.widthOfTextAtSize(trial,size)<=available) {current=trial;continue;}
      if (current) rows.push(current);
      current='';
      for (const char of word) {
        if (face.widthOfTextAtSize(current+char,size)>available && current) {rows.push(current);current='';}
        current+=char;
      }
    }
    if (current) rows.push(current);
    for (const row of rows) {
      if (y<margin+size*1.5) addPage();
      const dark = theme.dark && line.type==='h1';
      if (dark) page.drawRectangle({x:margin-8,y:y-size*1.25,width:available+16,height:size*1.65,color});
      const sectionPanel = line.type==='h2' && (theme.dark || theme.rail);
      if (sectionPanel) page.drawRectangle({x:margin-7,y:y-size*1.3,width:available+14,height:size*1.8,color:surface});
      const x = theme.centered && (line.type==='h1' || resume && identity && line.type==='text') ? margin+(available-face.widthOfTextAtSize(row,size))/2 : margin;
      page.drawText(row,{x,y:y-size,font:face,size,color:dark?rgb(1,1,1):line.type==='note'?muted:heading?color:ink});
      y-=size*1.5;
    }
    if (line.type==='h2' && body.design!=='minimal' && !theme.dark && !theme.rail) { page.drawLine({start:{x:margin,y:y+2},end:{x:width-margin,y:y+2},thickness:.6,color:rule}); y-=4; }
  }
  pdf.getPages().forEach((p,i)=>p.drawText(`${i+1} / ${pdf.getPageCount()}`,{x:width-margin-28,y:22,font,size:8,color:ink}));
  return pdf.save();
}
export async function createDocx(body) {
  const { Document, Packer, Paragraph, TextRun, ImageRun, HeadingLevel, AlignmentType, BorderStyle } = await import('docx');
  const theme = designFor(body.design);
  const photo = await photoBytes(body.photo);
  const children=[];
  if (photo) children.push(new Paragraph({alignment:theme.centered?AlignmentType.CENTER:AlignmentType.RIGHT,children:[new ImageRun({data:photo.bytes,type:photo.type,transformation:{width:Math.min(76,100*photo.width/photo.height),height:Math.min(100,76*photo.height/photo.width)}})]}));
  let identity = false;
  const resume = !body.document || body.document === 'cv';
  for (const line of parseLines(body.content)) {
    if (line.type === 'h1') identity = true;
    if (['h2','h3','bullet'].includes(line.type)) identity = false;
    const heading = line.type.startsWith('h');
    const level = {h1:HeadingLevel.TITLE,h2:HeadingLevel.HEADING_1,h3:HeadingLevel.HEADING_2}[line.type];
    children.push(new Paragraph({
      heading:level,
      alignment:theme.centered && (line.type==='h1' || resume && identity && line.type==='text') ? AlignmentType.CENTER:AlignmentType.LEFT,
      spacing:{before:line.type==='h1'?0:line.type==='h2'?260:heading?140:0,after:line.type==='blank'?60:100,line:300},
      widowControl:true,
      keepNext:heading,
      bullet:line.type==='bullet'?{level:0}:undefined,
      border:line.type==='h2' && body.design!=='minimal' && !theme.dark && !theme.rail ? {bottom:{color:theme.rule,style:BorderStyle.SINGLE,size:4}} : line.type==='h1' && theme.topbar ? {top:{color:theme.accent,style:BorderStyle.SINGLE,size:18,space:10}} : line.type==='h1' && theme.rail ? {left:{color:theme.accent,style:BorderStyle.SINGLE,size:24,space:10}} : undefined,
      shading:theme.dark && line.type==='h1'?{fill:theme.accent} : line.type==='h2' && (theme.dark || theme.rail) ? {fill:theme.surface} : undefined,
      children:[new TextRun({text:line.type==='h2' && theme.uppercase ? line.text.toUpperCase() : line.text,font:theme.font,bold:heading,italics:line.type==='note',color:theme.dark && line.type==='h1'?'FFFFFF':line.type==='note'?theme.muted:heading?theme.accent:theme.ink,size:line.type==='h1'?theme.nameSize*2:line.type==='h2'?theme.sectionSize*2:line.type==='note'?17:20})],
    }));
  }
  const doc = new Document({styles:{default:{document:{run:{font:theme.font,size:20,color:theme.ink},paragraph:{spacing:{line:300,after:100}}}}},sections:[{properties:{page:{size:{width:11906,height:16838},margin:{top:850,bottom:850,left:850,right:850}}},children}]});
  return Packer.toBlob(doc);
}
export async function exportDocument(body) {
  if (!body.content?.trim()) throw new Error('Kein Inhalt / no content.');
  const filename = (body.filename || 'Lebenslauf').replace(/[\\/:*?"<>|\x00-\x1f]/g,'_').replace(/\.(pdf|docx)$/i,'').slice(0,100) || 'Lebenslauf';
  if (body.format==='docx') return {blob:await createDocx(body),filename:`${filename}.docx`};
  if (body.format!=='pdf') throw new Error('Unbekanntes Format / unsupported format.');
  return {blob:new Blob([await createPdf(body)],{type:'application/pdf'}),filename:`${filename}.pdf`};
}
