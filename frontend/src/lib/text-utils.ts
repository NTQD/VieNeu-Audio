// Dem "tu" tieng Viet theo quy uoc pho bien cua da so cong cu dem tu (vd.
// Microsoft Word ban tieng Viet): tach theo khoang trang, dem so token -
// tieng Viet viet moi AM TIET cach nhau 1 khoang trang (vd. "Việt Nam" = 2
// token), KHONG phai NLP tach tu that su (can model rieng, qua nang cho 1
// bo dem don gian o UI). Day la cach dem "tu" nguoi dung pho thong hieu va
// mong doi khi thay o goc man hinh soan thao, khong phai dinh nghia ngon
// ngu hoc chat che.
export function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
}
