// vim: set sw=2:


function __load_and_transform_xml(el, url, cb)
{
  $.get(url, function(xml){
    if (xml.firstChild.nodeName != "xml-stylesheet")
      throw new Error("No stylesheet given")

    var xsl_proc = new XSLTProcessor ()
    xsl_url = xml.firstChild.data.match(/href='([^']+)/)[1]
    $.get(xsl_url, function(xsl) {
      xsl_proc.importStylesheet (xsl)
      $(el).empty().append(xsl_proc.transformToFragment (xml, document))
    }, "xml")
    if (cb != undefined)
    {
      cb()
    }
  })
}


(function( $ ){

  $.fn.load_xml = function(url) {
      this.each(function(idx, el) {
        $(el).addClass("loading")
        $(el).text("Loading …")
        __load_and_transform_xml(el, url, function() {
          $(el).removeClass("loading")
        })
      })
    };

})( jQuery );


$(document).ready(function(){
  $("div[load]").each(function(index,el){
    $(el).load_xml($(el).attr("load"))
  })

  $("h2").each(function(index, el) {
    var e = $(el)
    var anchor = e.text()
    e.append($("<a>").attr("id", anchor))
    var a = $("<a>").text(e.text())
    a.attr("href", "#" + anchor)
    var li = $("<li>").append(a)
    $("#toc").append(li)
  })

  setTimeout(function() {
    window.location.reload()
  }, 60*1000)

});
