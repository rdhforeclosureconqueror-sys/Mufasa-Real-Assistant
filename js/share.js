function shareResponse(text) {
  const url = window.location.href;
  const msg = `${text}\n— from Mufasa Real Assistant`;
  if (navigator.share) {
    navigator.share({ title: "Mufasa Real Assistant", text: msg, url });
  } else {
    const encoded = encodeURIComponent(msg + " " + url);
    window.open(`https://twitter.com/intent/tweet?text=${encoded}`, "_blank");
  }
}
