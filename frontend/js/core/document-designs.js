import designs from '../../../static/document-designs.json' with {type:'json'};

export const DESIGNS = designs;
export const designFor = id => designs[id] || designs.modern;
export const fontFiles = theme => ({
  regular:`Noto${theme.serif ? 'Serif' : 'Sans'}-Regular.ttf`,
  bold:`Noto${theme.serif ? 'Serif' : 'Sans'}-Bold.ttf`,
});
