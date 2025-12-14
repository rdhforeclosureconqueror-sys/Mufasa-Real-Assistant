function shareText(text) {
  if (navigator.share) {
    navigator.share({ text }).catch(()=>{});
  } else {
    navigator.clipboard.writeText(text);
    alert("Copied to clipboard ✅");
  }
}
