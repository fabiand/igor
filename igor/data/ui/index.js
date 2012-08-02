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
            var relicon = $("<div class='reload'><a href='javascript:void(0)'>↻ Reload</a></div>")
            relicon.hide()
            relicon.find("a").click(function(){$(el).load_xml(url);})
            $(ele).prepend(relicon)
            relicon.delay("slow").fadeIn()

            $(document).trigger("load", ele)
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

  // Load all marked divs
  $("div[load]").each(function(index,el){
    var url = $(el).attr("load")

    var hash = window.location.hash
    var is_in_hash = ("#"+$(el).attr("id")) == hash

    if ($(el).attr("on-request") && !is_in_hash)
    {
      $(el).html("Click to load from url (<a href='url'>source</a>).".replace(/url/g, url))
      $(el).click(function() {
        $(el).removeAttr("on-request")
        $(el).load_xml(url)
        $(el).unbind("click")
      })
    }
    else
    {
      $(el).load_xml(url)
      $(el).removeAttr("on-request")
    }
  })

  // Generate TOC from h2
  $("h2").each(function(index, el) {
    var e = $(el)
    var anchor = e.text()
    e.append($("<a>").attr("id", anchor))
    var a = $("<a>").text(e.text())
    a.attr("href", "#" + anchor)
    var li = $("<li>").append(a)
    $("#toc").append(li)
  })

  // Replace all timestamps
  $(document).on("load", function(ev, el) {
    $(el).find("span#convert-timestamp").each(function(idx, x) {
      var x = $(x)
      x.text(new Date(1000 * x.attr("timestamp")).toLocaleString())
    })
  })

/*  setTimeout(function() {
    window.location.reload()
  }, 60*1000)*/

});
