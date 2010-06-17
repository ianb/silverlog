$.fn.ajaxRender = function (options, declarations) {
  var selector = this.selector;
  if (typeof options == 'string') {
    options = {url: options};
  }
  options.success = function (result) {
    $(selector).render(result, declarations);
  };
  options.dataType = options.dataType || "json";
  return $.ajax(options);
};

var currentCheckpoint = null;

$(function () {

  $.ajax({
    url: "./api/checkpoint",
    dataType: "json",
    success: function (result) {
      $.each(result.checkpoints, function () {
        var el = $('<option></option>').attr('value', this.id).attr('title', this.date).text($.relatizeDate.timeAgoInWords(new Date(this.date), true));
        $('#checkpoint').append(el);
      });
      if ($.cookie('checkpoint')) {
        $('#checkpoint option[value="'+$.cookie('checkpoint')+'"]').select();
      }
      $('#checkpoint').append(
        $('<option id="checkpoint-add-new" value="__new__">New checkpoint</option>'));
      $('#checkpoint').bind('change', function () {
        currentCheckpoint = $('#checkpoint').val() || null;
        $.cookie('checkpoint', currentCheckpoint || '');
        if (currentCheckpoint == "__new__") {
          $.ajax({
            url: "./api/checkpoint",
            dataType: "json",
            type: "POST",
            success: function (result) {
              var el = $('<option></option>').attr('value', result.checkpoint.id).attr('title', result.checkpoint.date).text($.relatizeDate.timeAgoInWords(new Date(result.checkpoint.date), true));
              $('#checkpoint-add-new').before(el);
              el.select();
              $.cookie('checkpoint', result.checkpoint.id);
            }
          });
        }
      });
    }
  });

});

function addCheckpoint(url) {
  if (! currentCheckpoint) {
    return url;
  } else {
    if (url.indexOf('?') == -1) {
      url += '?';
    } else {
      url += '&';
    }
    url += 'checkpoint=' + currentCheckpoint;
    return url;
  }
}

var app = $.sammy(function () {
  this.element_selector = '#body';

  this.get('#/', function (context) {
    moveScreen('#main');
    $('#main #log-list li:nth-child(1n+2)').remove();
    $('#main #skipped-list li:nth-child(1n+2)').remove();
    $('#header #title-slot').text('index');

    $('#main').ajaxRender(
      "./api/list-logs",
      {
        "#log-list li": {
          "log<-logs": {
            "a": "log.description",
            "a@href": function (ctx) {
              return '#/view/'+ctx.item.id;
            }
          }
        }
      });

    $.ajax({
      url: "./api/skipped-files",
      dataType: "json",
      success: function (result) {
        $('#main').render(
          result,
          {
            "#skipped-list li": {
              "skipped_file<-skipped_files": {
                ".": "skipped_file"
              }
            }
          });
        if (! result.skipped_files.length) {
          $('#skipped-list').hide();
          $('#skipped-list-title').hide();
        } else {
          $('#skipped-list').show();
          $('#skipped-list-title').show();
        }
      }
    });

  });

  this.get('#/view/:log_id', function (context) {
    moveScreen('#log-view');
    $('#header #title-slot').text('Loading...');
    $.ajax({
      url: addCheckpoint("./api/log/" + this.params.log_id + "?nocontent"),
      dataType: "json",
      success: function (result) {
        var log_type = result.log_type;
        if (! templateRules[log_type]) {
          log_type = "default";
        }
        $('#header #title-slot').text(result.description);
        $('#log-view .log-view').remove();
        var tmpl = $('.template-'+log_type);
        tmpl = tmpl.clone();
        tmpl.removeClass('template-'+log_type);
        tmpl.show();
        tmpl.addClass('log-view');
        $('#log-view').append(tmpl);
        tmpl = tmpl.render(
          result,
          templateRules[log_type]);
        $('.date', tmpl).relatizeDate();
      }
    });
  });

});

$(function () {
  app.run('#/');
});

templateRules = {

  "default": {
    "div.log-section": {
      "chunk<-chunks": {
        "code.log-line": "chunk.data"
      }
    }
  },

  "apache_access_log": {
    "tr.log-section": {
      "chunk<-chunks": {
        ".log-date": "chunk.date",
        ".log-date@title": "chunk.date",
        ".log-method": "chunk.method",
        ".log-path": "chunk.path",
        ".log-response_code": "chunk.response_code",
        ".log-response_code@class+": function (ctx) {
          return " response-code-"+ctx.item.response_code;
        },
        ".log-response_bytes": "chunk.response_bytes",
        ".log-referrer": function (ctx) {
          var ref = ctx.item.referrer;
          var host = ctx.item.host;
          if (ref == "-")
            return "";
          if (ref.substr(7, host.length) == host) {
            return ref.substr(host.length+7);
          }
          return ref.substr(ref.indexOf('://')+3);
        },
        ".log-referrer@href": function (ctx) {
          return ctx.item.referrer == "-" ? "" : ctx.item.referrer;
        },
        ".log-user_agent": "chunk.user_agent",
        ".log-host": function (ctx) {
          var host = ctx.item.host;
          if (host == "-") {
            return "";
          }
          var idx = host.indexOf(".");
          if (idx != -1) {
              return host.substr(0, idx);
          }
          return host;
        },
        ".log-host@title": "chunk.host",
        ".log-host@href": function (ctx) {
          return ctx.item.host == "-" ? "" : "http://"+ctx.item.host;
        },
        ".log-app_name": "chunk.app_name",
        ".log-time": function (ctx) {return ctx.item.milliseconds/1000000;}
      }
    }
  },

  "apache_error_log": {
    "div.log-section": {
      "chunk<-chunks": {
        ".log-warning-level": "chunk.level",
        ".log-warning-level@class+": function (ctx) {return " log-warning-level-"+ctx.item.level;},
        ".log-date@title": "chunk.date",
        ".log-date": "chunk.date",
        ".log-client": "chunk.remote_addr",
        ".log-message": "chunk.message"
      }
    }
  },

  "apache_rewrite_log": {
    "div.log-section": {
      "chunk<-chunks": {
        ".log-date": "chunk.date",
        ".log-date@title": "chunk.date",
        ".log-remote_addr": "chunk.remote_addr",
        ".log-message": "chunk.message"
      }
    }
  },

  "silver_error_log": {
    "div.log-section": {
      "chunk<-chunks": {
        ".log-date": "chunk.date",
        ".log-method": "chunk.method",
        ".log-path": "chunk.path",
        ".log-message": "chunk.message"
      }
    }
  }

};

var currentScreen = null;

function moveScreen(selector) {
  if (currentScreen) {
    $(currentScreen).hide();
    currentScreen = null;
  }
  var el = $(selector);
  currentScreen = selector;
  el.show();
  return el;
}

function catcher(func) {
  return function () {
    try {
      return func.apply(this, arguments);
    } catch (e) {
      Sammy.log('Got exception in function', func, e);
      throw(e);
    }
  };
}
