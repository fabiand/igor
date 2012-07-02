// vim: set sw=2:


function __load_and_transform_xml(el, url, cb)
{
  $.get(url, function(xml){
    if (xml.firstChild.nodeName != "xml-stylesheet")
      throw new Error("No stylesheet given")

    var xsl_proc = new XSLTProcessor ()
    var xsl_url = xml.firstChild.data.match(/href='([^']+)/)[1]
    $.get(xsl_url, function(xsl) {
      xsl_proc.importStylesheet (xsl)
      var fragment = xsl_proc.transformToFragment (xml, document)
      $(el).slideUp(function() {
        $(el).empty().append(fragment).slideDown("slow")
        if (cb != undefined)
        {
          cb(el)
        }
      })
    }, "xml")
  })
}


(function( $ ){

  $.fn.load_xml = function(url) {
      this.each(function(idx, el) {
        $(el).addClass("loading")
        $(el).html("Loading from <a href='url'>url</a>".replace(/url/g, url))
        __load_and_transform_xml(el, url, function(ele) {
          $(ele).removeClass("loading")
//          $(ele).add_table_footer("Source: " + url)
        })
      })
    };

  $.fn.add_table_footer = function(text) {
    var footer = $("<tfoot><tr><td>abc</td></tr></tfoot>")
    footer.find("td").html(text)
    this.find("table").append(footer)
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
