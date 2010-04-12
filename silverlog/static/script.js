var app = $.sammy(function () {
  this.element_selector = '#body';

  this.get('#/', function (context) {
    moveScreen('#main');
    $('#main #log-list li:nth-child(1n+2)').remove();
    $('#header #title-slot').text('index');
    $.ajax({
      url: "/api/list-logs",
      dataType: "json",
      success: function (result) {
        $('#main').render(
          result,
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
      }
    });
  });

  this.get('#/view/:log_id', function (context) {
    moveScreen('#log-view');
    $.ajax({
      url: "/api/log/"+this.params.log_id,
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
        console.log('rule', templateRules[log_type]);
        console.log('data', result);
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
        ".log-method": "chunk.method",
        ".log-path": "chunk.path",
        ".log-response_code": "chunk.response_code",
        ".log-response_bytes": "chunk.response_bytes",
        ".log-referrer": function (ctx) {return ctx.item.referrer == "-" ? "" : ctx.item.referrer},
        ".log-referrer@href": function (ctx) {return ctx.item.referrer == "-" ? "" : ctx.item.referrer},
        ".log-user_agent": "chunk.user_agent",
        ".log-host": "chunk.host",
        ".log-host@href": function (ctx) {return "http://"+ctx.item.host;},
        ".log-app_name": "chunk.app_name",
        ".log-milliseconds": "chunk.milliseconds"
      }
    }
  },

  "apache_error_log": {
    "div.log-section": {
      "chunk<-chunks": {
        ".log-warning-level": "chunk.level",
        ".log-warning-level@class+": function (ctx) {return " log-warning-level-"+ctx.item.level},
        ".log-date": "chunk.date",
        ".log-client": "chunk.remote_addr",
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
